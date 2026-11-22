#!/usr/bin/env bash
# =============================================================================
# snowflake/keys/generate_keypair.sh
#
# Creates the RSA key pair used by the dlt_dev service user.
#
# WHY IT LIVES HERE AND NOT IN THE REPO: the private key must never be in git,
# in a Docker image or in .env. The pair is written to a directory OUTSIDE the
# working tree (default ~/.snowflake/keys/github_raw/dlt_dev) with mode 600/700,
# so neither git nor the Astro build context can ever see it.
#
# WHAT IT PRODUCES (per Snowflake's key-pair docs)
#   rsa_key.p8        private key, unencrypted PKCS#8 PEM
#                     (openssl genrsa 2048 | openssl pkcs8 -topk8 -nocrypt)
#   rsa_key.pub       public key, PEM (openssl rsa -pubin)
#   rsa_key.pub.b64   public key, base64 DER, single line -> the value the SQL
#                     script expects as DLT_DEV_PUBLIC_KEY
#   rsa_key.pub.sha256  SHA-256 fingerprint, must equal RSA_PUBLIC_KEY_FP
#
# WHY UNENCRYPTED: an encrypted key needs a passphrase at every connect. dlt
# supports it (private_key_passphrase), but then the passphrase becomes another
# secret to store - the very thing this ticket bans. 700/600 permissions on a
# dedicated directory are the control instead. Rotate with:
#       snow sql --role USERADMIN ... ALTER USER dlt_dev ROTATE KEY PAIR ...
#
# USAGE:  ./snowflake/keys/generate_keypair.sh
#         KEY_DIR=/some/other/dir ./snowflake/keys/generate_keypair.sh
# =============================================================================
set -euo pipefail

KEY_DIR="${KEY_DIR:-$HOME/.snowflake/keys/github_raw/dlt_dev}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

# --- Safety rails -----------------------------------------------------------
if [[ "$KEY_DIR" == "$REPO_ROOT"/* ]]; then
  echo "refusing to write key material inside the repository: $KEY_DIR" >&2
  exit 1
fi
if [[ -e "$KEY_DIR/rsa_key.p8" ]]; then
  echo "KEY_DIR already contains a private key: $KEY_DIR" >&2
  echo "Rotate deliberately (ALTER USER ... ROTATE KEY PAIR) instead of overwriting." >&2
  exit 1
fi
for bin in openssl base64; do
  command -v "$bin" >/dev/null || { echo "missing: $bin" >&2; exit 1; }
done

umask 077
mkdir -p "$KEY_DIR"

# --- Generate ---------------------------------------------------------------
# 2048 bits is Snowflake's documented minimum RS256 key size.
openssl genrsa 2048 2>/dev/null | openssl pkcs8 -topk8 -nocrypt -inform PEM -out "$KEY_DIR/rsa_key.p8"
openssl rsa -in "$KEY_DIR/rsa_key.p8" -pubout -out "$KEY_DIR/rsa_key.pub" 2>/dev/null

# base64 DER, single line, header/footer stripped: what ALTER USER expects.
openssl rsa -pubin -in "$KEY_DIR/rsa_key.pub" -outform DER 2>/dev/null \
  | base64 | tr -d '\n' > "$KEY_DIR/rsa_key.pub.b64"

# Fingerprint Snowflake will report as RSA_PUBLIC_KEY_FP ("SHA256:<b64>").
printf 'SHA256:%s' "$(openssl rsa -pubin -in "$KEY_DIR/rsa_key.pub" -outform DER 2>/dev/null \
  | openssl dgst -sha256 -binary | base64)" > "$KEY_DIR/rsa_key.pub.sha256"

chmod 600 "$KEY_DIR"/rsa_key.*
chmod 700 "$KEY_DIR"

# --- Report (never the private key itself) ----------------------------------
cat <<EOF
key pair created in $KEY_DIR (outside the repository)
  private key : rsa_key.p8        600  <- never commit, never print
  public key  : rsa_key.pub       600  (PEM, for humans)
  sql value   : rsa_key.pub.b64   600  (base64 DER, feed as DLT_DEV_PUBLIC_KEY)
  fingerprint : $(cat "$KEY_DIR/rsa_key.pub.sha256")
EOF
