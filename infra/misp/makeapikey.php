<?php
// Generate a new MISP API auth key for user_id 1 (admin).
//
// The DB password is read from the environment only — never hardcode it here.
// The misp-core container already receives MYSQL_PASSWORD from
// docker-compose.misp.yml (sourced from .env.misp), so the usual invocation is:
//
//   docker cp makeapikey.php <misp-core>:/tmp/makeapikey.php
//   docker exec <misp-core> php /tmp/makeapikey.php

function require_env(array $names): string
{
    foreach ($names as $name) {
        $value = getenv($name);
        if ($value !== false && $value !== '') {
            return $value;
        }
    }
    fwrite(STDERR, "ERROR: required environment variable not set: " . implode(' or ', $names) . PHP_EOL);
    exit(1);
}

$dbHost = getenv('MYSQL_HOST') ?: 'misp-db';
$dbName = getenv('MYSQL_DATABASE') ?: 'misp';
$dbUser = getenv('MYSQL_USER') ?: 'misp';
$dbPass = require_env(['MISP_DB_PASSWORD', 'MYSQL_PASSWORD']);

$pdo = new PDO("mysql:host={$dbHost};dbname={$dbName}", $dbUser, $dbPass);

$authkey = bin2hex(random_bytes(20));
$hashed  = password_hash($authkey, PASSWORD_BCRYPT);

$stmt = $pdo->prepare("INSERT INTO auth_keys (uuid, authkey, authkey_start, authkey_end, user_id, created, expiration, read_only, allowed_ips, comment) VALUES (UUID(), ?, ?, ?, 1, UNIX_TIMESTAMP(), 0, 0, NULL, 'SOC Brain auto-generated')");
$stmt->execute([$hashed, substr($authkey, 0, 4), substr($authkey, -4)]);

echo "API Key (save this): " . $authkey . PHP_EOL;
