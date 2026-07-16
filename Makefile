.PHONY: validate dry-run doctor

validate:
	bash validation/validate.sh

dry-run:
	bash bin/workstation-bootstrap dry-run

doctor:
	bash bin/workstation-doctor --full
