.PHONY: help status inventory dry-run validate doctor auth-doctor package install reconcile

help:
	@printf '%s\n' \
	  'Engineering Workstation Bootstrap' \
	  '' \
	  'Read-only and local commands:' \
	  '  make help          Show this command service' \
	  '  make status        Show bootstrap readiness status' \
	  '  make inventory     Inspect host tools and capabilities' \
	  '  make dry-run       Preview the selected workstation profile' \
	  '  make validate      Validate repository scripts and package output' \
	  '  make doctor        Run the full workstation doctor' \
	  '  make auth-doctor   Validate GitHub and Cloudflare authentication' \
	  '  make package       Build archive and checksum; set VERSION=<version>' \
	  '' \
	  'Mutating commands:' \
	  '  make install       Run the guided first-time bootstrap' \
	  '  make reconcile     Repair declared workstation drift' \
	  '' \
	  'Optional variable:' \
	  '  WORKSTATION_PROFILE=mac-studio|macbook|linux-workstation|remote-codex-host'

status:
	bash bin/workstation-bootstrap status

inventory:
	bash bin/environment-inventory

dry-run:
	bash bin/workstation-bootstrap dry-run

validate:
	bash validation/validate.sh

doctor:
	bash bin/workstation-doctor --full

auth-doctor:
	@bash bin/github-auth-doctor; github_status=$$?; \
	bash bin/cloudflare-auth-doctor; cloudflare_status=$$?; \
	test $$github_status -eq 0 -a $$cloudflare_status -eq 0

package:
	bash packaging/build-package.sh "$${VERSION:-0.1.0-dev}"

install:
	bash bin/workstation-bootstrap install

reconcile:
	bash bin/workstation-bootstrap reconcile
