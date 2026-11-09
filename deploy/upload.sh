#!/usr/bin/env bash
set -Eeuo pipefail

: "${DEPLOY_HOST:?Set the DEPLOY_HOST repository variable}"
: "${DEPLOY_SSH_KEY:?Set the DEPLOY_SSH_KEY repository secret}"
: "${DEPLOY_KNOWN_HOSTS:?Set the DEPLOY_KNOWN_HOSTS repository variable}"

[[ "$DEPLOY_HOST" =~ ^[a-zA-Z0-9][a-zA-Z0-9.-]*$ ]] || {
  echo 'Invalid deployment host.' >&2
  exit 1
}
[[ -s dist/index.html && -s dist/deployment.json ]] || {
  echo 'Build output or deployment marker is missing.' >&2
  exit 1
}
if [[ -n "$(find dist -type l -print -quit)" ]]; then
  echo 'The static build must not contain symbolic links.' >&2
  exit 1
fi

umask 077
deploy_ssh_dir=$(mktemp -d)
trap 'rm -rf -- "$deploy_ssh_dir"' EXIT
printf '%s\n' "$DEPLOY_SSH_KEY" > "$deploy_ssh_dir/key"
unset DEPLOY_SSH_KEY
printf '%s\n' "$DEPLOY_KNOWN_HOSTS" > "$deploy_ssh_dir/known_hosts"
cat > "$deploy_ssh_dir/config" <<EOF
Host landing-production
  HostName $DEPLOY_HOST
  User crmapp
  Port 22
  IdentityFile $deploy_ssh_dir/key
  IdentitiesOnly yes
  BatchMode yes
  PasswordAuthentication no
  StrictHostKeyChecking yes
  UserKnownHostsFile $deploy_ssh_dir/known_hosts
  ConnectTimeout 15
  ServerAliveInterval 15
  ServerAliveCountMax 3
EOF

# The server forces this key through rrsync into /var/www/crm/landing.
# Its remote "." is that restricted directory, never the account's home.
rsync --recursive --times --perms --compress --checksum \
  --delete --delay-updates --chmod=Du=rwx,Dgo=rx,Fu=rw,Fgo=r \
  --rsh="ssh -F $deploy_ssh_dir/config" \
  dist/ landing-production:.
