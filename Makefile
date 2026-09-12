.PHONY: help status inventory private-profile dry-run validate doctor toolsets-doctor auth-doctor package package-drive install activate reconcile repair rollback

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
	  '  make toolsets-doctor Check coding-agent and shared tool versions' \
	  '  make auth-doctor   Validate configured authentication providers' \
	  '  make package       Build archive and checksum; set VERSION=<version>' \
	  '  make private-profile Generate a local, secret-free endpoint overlay' \
	  '  make package-drive Publish with an explicit publication contract' \
	  '' \
	  'Mutating commands:' \
	  '  make install       Run prerequisites, then require an activation contract' \
	  '  make activate      Transactionally activate with ACTIVATION_CONTRACT=<file>' \
	  '  make reconcile     Reconcile a disposable staged target only' \
	  '  make repair        Validate and reconcile a staged target only' \
	  '  make rollback      Restore a transaction with ROLLBACK_RECEIPT=<file>' \
	  '' \
	  'Optional variable:' \
	  '  WORKSTATION_PROFILE=macos-desktop|linux-workstation'

status:
	bash bin/workstation-bootstrap status

inventory:
	bash bin/environment-inventory

private-profile:
	bash bin/workstation-private-profile inventory --output "$${PRIVATE_PROFILE:-.local/tony-private-profile.json}"

dry-run:
	bash bin/workstation-bootstrap dry-run

validate:
	bash validation/validate.sh

doctor:
	bash bin/workstation-doctor --full

toolsets-doctor:
	bash bin/workstation-toolsets doctor

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

package-drive:
	@if [ -n "$${PRIVATE_PROFILE:-}" ]; then \
	  bash bin/workstation-publish-drive --publication-contract "$${PUBLICATION_CONTRACT:?set PUBLICATION_CONTRACT}" --version "$${VERSION:-0.1.0-dev}" --private-profile "$$PRIVATE_PROFILE"; \
	else \
	  bash bin/workstation-publish-drive --publication-contract "$${PUBLICATION_CONTRACT:?set PUBLICATION_CONTRACT}" --version "$${VERSION:-0.1.0-dev}"; \
	fi

install:
	bash bin/workstation-bootstrap install

activate:
	@if [ -n "$${PRIVATE_PROFILE:-}" ]; then \
	  bash bin/workstation-activate --activation-contract "$${ACTIVATION_CONTRACT:?set ACTIVATION_CONTRACT}" --private-profile "$$PRIVATE_PROFILE"; \
	else \
	  bash bin/workstation-activate --activation-contract "$${ACTIVATION_CONTRACT:?set ACTIVATION_CONTRACT}"; \
	fi

reconcile:
	bash bin/staged-workstation reconcile

repair:
	bash bin/staged-workstation repair

rollback:
	@if [ -n "$${ROLLBACK_RECEIPT:-}" ]; then bash bin/workstation-rollback --receipt "$$ROLLBACK_RECEIPT"; else bash bin/workstation-rollback --latest; fi
