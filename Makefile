.PHONY: validate dry-run doctor package

validate:
	bash validation/validate.sh

dry-run:
	bash bin/workstation-bootstrap dry-run

doctor:
	bash bin/workstation-doctor --full

package:
	bash packaging/build-package.sh "$${VERSION:-0.1.0-dev}"
