#!/usr/bin/env node
// Issue #26: read-only managed Skills inventory. Canonical evaluation is Skills #323.
import {readFileSync, existsSync, realpathSync, mkdtempSync, writeFileSync, rmSync, readdirSync} from 'node:fs';
import {execFileSync} from 'node:child_process';
import {join, resolve, dirname, sep} from 'node:path';
import {tmpdir} from 'node:os';
import {createHash} from 'node:crypto';
const opts=new Map();
for(let i=2;i<process.argv.length;i+=2){
  const k=process.argv[i],v=process.argv[i+1];
  if(!k?.startsWith('--')||!v||opts.has(k))throw Error('INVALID_ARGUMENT');
  opts.set(k,v);
}
const need=k=>{const v=opts.get('--'+k);if(!v)throw Error('REQUIRED_'+k.toUpperCase());return v};
const parse=p=>JSON.parse(readFileSync(p,'utf8'));
const sha=b=>'sha256:'+createHash('sha256').update(b).digest('hex');
const root=realpathSync(resolve(need('skills-root')));
const host=need('host-id');
const heads=execFileSync('git',['-C',root,'rev-parse','HEAD'],{encoding:'utf8'}).trim();
if(execFileSync('git',['-C',root,'status','--porcelain'],{encoding:'utf8'}).trim())throw Error('CANONICAL_SOURCE_DIRTY');
const registrySha256=sha(readFileSync(join(root,'registry/skills.json')));
const current=parse(join(root,'registry/current-skills.json'));
if(current.registryDigest!==registrySha256)throw Error('CANONICAL_REGISTRY_DRIFT');
const active=new Set(current.skills.filter(x=>x.status==='active').map(x=>x.invocation));
const profile=opts.get('--profile-file')?parse(resolve(opts.get('--profile-file'))):null;
const surfaces=[];
for(const kind of ['codex','agents']){
  const entryRoot=opts.get('--'+kind+'-root');if(!entryRoot)continue;
  const managedRoot=realpathSync(resolve(entryRoot));
  const library=realpathSync(join(dirname(managedRoot),'skill-library'));
  const observed=[],anomalies=[];
  for(const e of readdirSync(managedRoot,{withFileTypes:true})){
    if(!e.isDirectory()||e.name.startsWith('.'))continue;
    const invocation='$'+e.name;if(!active.has(invocation))continue;
    const wrapper=join(managedRoot,e.name,'SKILL.md');
    if(!existsSync(wrapper)){anomalies.push({invocation,reason:'MISSING_WRAPPER'});continue}
    const line=readFileSync(wrapper,'utf8').split('\n').find(x=>x.includes('Read and follow the complete skill at '))||'';
    const target=line.split(String.fromCharCode(96))[1];
    if(!target||!existsSync(target)){anomalies.push({invocation,reason:'MANAGED_TARGET_MISSING'});continue}
    const real=realpathSync(target);
    if(!real.startsWith(library+sep)){anomalies.push({invocation,reason:'TARGET_OUTSIDE_MANAGED_LIBRARY'});continue}
    const file=join(dirname(real),'runtime-manifest.json');
    if(!existsSync(file)){anomalies.push({invocation,reason:'RUNTIME_MANIFEST_MISSING'});continue}
    const manifest=parse(file);
    if(manifest.invocation!==invocation){anomalies.push({invocation,reason:'INVOCATION_MISMATCH'});continue}
    observed.push({
      invocation,version:manifest.version||null,
      manifestSha256:manifest.governedCapability?.manifestSha256||null,
      selected:manifest.runtimeConsumption?.selected===true,
      materialized:manifest.runtimeConsumption?.materialized===true,
      invoked:manifest.runtimeConsumption?.invoked===true,
      consumed:manifest.runtimeConsumption?.consumed===true,
      executionReceipt:null,conformanceVerified:false,
    });
  }
  const assigned=profile?.surfaces?.find(x=>x.kind===kind);
  surfaces.push({
    id:host+':'+kind+'-managed',
    runtime:kind==='codex'?'codex-cli-managed':'agent-skills-managed',
    profileAuthority:assigned?.ownerApproved===true&&assigned.authority?
      assigned.authority:'UNVERIFIED_PROFILE:engineering-workstation-bootstrap#26',
    observedAt:new Date().toISOString(),
    observationState:anomalies.length?'PARTIAL':'OBSERVED',
    observed,required:assigned?.required||[],anomalies,
  });
}
if(!surfaces.length)throw Error('NO_MANAGED_ROOTS');
const observation={schema:'ghostmesh-fleet-skill-observation-v1',
  canonical:{commit:heads,registrySha256},surfaces};
let tmp;
try{
  tmp=mkdtempSync(join(tmpdir(),'gm-managed-skills-'));
  const input=join(tmp,'observation.json');
  writeFileSync(input,JSON.stringify(observation));
  const validator=join(root,'scripts/validate_issue_323_fleet_skills.mjs');
  if(!existsSync(validator))throw Error('CANONICAL_VALIDATOR_UNAVAILABLE');
  const output=JSON.parse(execFileSync(process.execPath,[validator,'--observation',input],{encoding:'utf8'}));
  console.log(JSON.stringify({
    schema:'ghostmesh-managed-workstation-skill-preflight-v1',
    canonical:output.source,coverage:output.coverage,
    fleetScopeDeclared:output.fleetScopeDeclared,
    surfaces:output.surfaces,
    anomalies:surfaces.map(x=>({surface:x.id,items:x.anomalies})),
    limits:['read-only','no-trusted-profile-without-owner-evidence','no-installed-runtime-promotion'],
  },null,2));
}finally{if(tmp)rmSync(tmp,{recursive:true,force:true})}
