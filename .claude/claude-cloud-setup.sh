#!/bin/bash
# Setup script of the claude-mods Claude cloud environment. Its sessions run triage and review
# work that needs only git and gh, which the cloud image already has, so it installs nothing.
# ponytail: no tool pre-warm; add `mise install` steps here when cloud sessions run this repo's tasks.
# It always exits 0, since a non-zero exit fails the whole cloud session.
echo "setup $(date -u +%FT%TZ) user=$(id -un)" >> /tmp/cloud-setup.log
exit 0
