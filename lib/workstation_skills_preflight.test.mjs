import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtempSync,mkdirSync,writeFileSync,rmSync,chmodSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {fileURLToPath} from 'node:url';
import {execFileSync,spawnSync} from 'node:child_process';
import {createHash} from 'node:crypto';
const script=fileURLToPath(new URL('./workstation_skills_preflight.mjs',import.meta.url));
function fixture(){
  const root=mkdtempSync(join(tmpdir(),'managed-skills-fixture-'));
  const source=join(root,'source');
  for(const dir of ['registry','scripts'])mkdirSync(join(source,dir),{recursive:true});
  const registry=JSON.stringify({skills:[]});
  writeFileSync(join(source,'registry/skills.json'),registry);
  writeFileSync(join(source,'registry/current-skills.json'),JSON.stringify({
    registryDigest:'sha256:'+createHash('sha256').update(registry).digest('hex'),skills:[]
  }));
  // Observe the exact input given to the canonical evaluator. The evaluator's
  // real conformance rules remain solely in the external canonical repository.
  writeFileSync(join(source,'scripts/validate_issue_323_fleet_skills.mjs'),`
    import {readFileSync} from 'node:fs';
    const observation=JSON.parse(readFileSync(process.argv[3],'utf8'));
    console.log(JSON.stringify({source:observation.canonical,coverage:'NOT_PROVEN',
      fleetScopeDeclared:false,surfaces:observation.surfaces}));
  `);
  execFileSync('git',['init','-q',source]);
  execFileSync('git',['-C',source,'add','.']);
  execFileSync('git',['-C',source,'-c','user.name=Fixture','-c','user.email=fixture@example.invalid','commit','-qm','synthetic canonical input']);
  const profile=join(root,'profile.json');
  writeFileSync(profile,JSON.stringify({surfaces:[{kind:'codex',ownerApproved:true,
    authority:'fixture:explicit-profile',required:[{invocation:'$required-fixture'}]}]}));
  return {root,source,profile,close(){rmSync(root,{recursive:true,force:true});},
    run(args){return spawnSync(process.execPath,[script,'--skills-root',source,'--host-id','fixture',
      '--profile-file',profile,...args],{encoding:'utf8',timeout:10000});}};
}
function output(result){assert.equal(result.status,0,result.stderr);return JSON.parse(result.stdout);}
for(const problem of ['missing-root','root-is-file','missing-library','library-is-file','library-no-read','library-no-search']){
  const permissions=problem.startsWith('library-no-');
  test(`managed observation returns UNOBSERVED for ${problem}`,{skip:permissions&&(process.platform==='win32'||process.getuid?.()===0)},()=>{
    const f=fixture();
    const library=join(f.root,'managed','skill-library');
    try{
      const managed=join(f.root,'managed','codex-skills');
      mkdirSync(join(f.root,'managed'),{recursive:true});
      if(problem==='root-is-file')writeFileSync(managed,'not a directory');
      if(problem.startsWith('missing-library')||problem==='library-is-file'||permissions)mkdirSync(managed);
      if(problem==='library-is-file')writeFileSync(join(f.root,'managed','skill-library'),'not a directory');
      if(permissions){mkdirSync(library);chmodSync(library,problem==='library-no-read'?0o111:0o444);}
      const result=f.run(['--codex-root',managed,'--agents-root',join(f.root,'absent-agent-root')]);
      const report=output(result);
      assert.equal(report.coverage,'NOT_PROVEN');
      assert.equal(report.fleetScopeDeclared,false);
      assert.equal(report.surfaces.length,2);
      assert.equal(report.surfaces[0].observationState,'UNOBSERVED');
      assert.deepEqual(report.surfaces[0].observed,[]);
      assert.deepEqual(report.surfaces[0].required,[{invocation:'$required-fixture'}]);
      assert.equal(report.surfaces[0].profileAuthority,'fixture:explicit-profile');
      assert.equal(report.anomalies[0].items[0].reason,
        problem==='missing-root'||problem==='root-is-file'?'MANAGED_ROOT_UNAVAILABLE':'MANAGED_LIBRARY_UNAVAILABLE');
      assert.equal(report.anomalies[1].items[0].reason,'MANAGED_ROOT_UNAVAILABLE');
      assert.equal(result.stderr,'');
      assert.ok(!result.stdout.includes(f.root),'private filesystem paths must not leak');
    }finally{if(permissions)chmodSync(library,0o700);f.close();}
  });
}
test('an empty available managed root stays observed with no inferred profile or consumption',()=>{
  const f=fixture();
  try{
    const managed=join(f.root,'managed','codex-skills');
    mkdirSync(managed,{recursive:true});mkdirSync(join(f.root,'managed','skill-library'));
    const report=output(f.run(['--codex-root',managed]));
    assert.equal(report.surfaces[0].observationState,'OBSERVED');
    assert.deepEqual(report.surfaces[0].observed,[]);
    assert.equal(report.coverage,'NOT_PROVEN');
    assert.deepEqual(report.anomalies[0].items,[]);
  }finally{f.close();}
});
