#!/usr/bin/env bash
set -Eeuo pipefail

: "${LANDING_URL:?Set the LANDING_URL repository variable}"
: "${GITHUB_SHA:?Set the expected deployment commit}"
[[ "$LANDING_URL" == https://* && "$LANDING_URL" != *'?'* && "$LANDING_URL" != *'#'* ]] || {
  echo 'LANDING_URL must be the HTTPS homepage without a query or fragment.' >&2
  exit 1
}

verify_dir=$(mktemp -d)
trap 'rm -rf -- "$verify_dir"' EXIT
landing_base=${LANDING_URL%/}
curl_options=(--silent --show-error --fail --location --connect-timeout 10 --max-time 30 --proto '=https' --proto-redir '=https')

for attempt in 1 2 3 4 5; do
  if homepage_status=$(curl "${curl_options[@]}" \
    --output "$verify_dir/index.html" --write-out '%{http_code}' \
    "$landing_base/?deployment=$GITHUB_SHA") && \
    [[ "$homepage_status" == 200 ]] && \
    curl "${curl_options[@]}" --output "$verify_dir/deployment.json" \
      "$landing_base/deployment.json?deployment=$GITHUB_SHA" && \
    node --input-type=module - "$verify_dir" <<'JS'
import { readFileSync } from "node:fs";
import { createHash } from "node:crypto";
const directory = process.argv[2];
const actual = JSON.parse(readFileSync(`${directory}/deployment.json`, "utf8"));
const expected = JSON.parse(readFileSync("dist/deployment.json", "utf8"));
const homepageHash = createHash("sha256").update(readFileSync(`${directory}/index.html`)).digest("hex");
if (actual.commit !== process.env.GITHUB_SHA || actual.commit !== expected.commit ||
    actual.indexSha256 !== expected.indexSha256 || homepageHash !== expected.indexSha256) {
  console.error("The public homepage does not match the build for this commit.");
  process.exit(1);
}
JS
  then
    echo "Verified: homepage HTTP 200; commit $GITHUB_SHA; HTML matches the Actions build."
    if [[ -n "${GITHUB_STEP_SUMMARY:-}" ]]; then
      {
        printf '### Landing deployed\n\n'
        printf -- '- Homepage: [%s](%s) — HTTP 200\n' "$LANDING_URL" "$LANDING_URL"
        printf -- '- Commit: `%s`\n' "$GITHUB_SHA"
        printf -- '- Public HTML checksum matches the Actions build.\n'
      } >> "$GITHUB_STEP_SUMMARY"
    fi
    exit 0
  fi
  echo "Verification attempt $attempt failed." >&2
  if [[ "$attempt" != 5 ]]; then
    sleep 3
  fi
done

echo 'Deployment verification failed. Fix the problem and push a new commit to main.' >&2
exit 1
