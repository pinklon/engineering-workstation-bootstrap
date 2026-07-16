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
	  '  make auth-doctor   Validate configured authentication providers' \
	  '  make package       Build archive and checksum; set VERSION=<version>' \
	  '' \
	  'Mutating commands:' \
	  '  make install       Run the guided first-time bootstrap' \
	  '  make reconcile     Repair declared workstation drift' \
	  '' \
	  'Optional variable:' \
	  '  WORKSTATION_PROFILE=macos-desktop|linux-workstation'

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
	if command -v wrangler >/dev/null 2>&1; then \
	  bash bin/cloudflare-auth-doctor; cloud_status=$$?; \
	else \
	  printf 'SKIP  Optional Cloudflare provider is not installed\n'; cloud_status=0; \
	fi; \
	test $$github_status -eq 0 -a $$cloud_status -eq 0

package:
	bash packaging/build-package.sh "$${VERSION:-0.1.0-dev}"

install:
	bash bin/workstation-bootstrap install

reconcile:
	bash bin/workstation-bootstrap reconcile
