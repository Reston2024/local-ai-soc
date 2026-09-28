<?php
// Reset the MISP admin password directly in the database.
//
// Secrets are read from the environment only — never hardcode them here.
// The misp-core container already receives MYSQL_PASSWORD, ADMIN_EMAIL and
// ADMIN_PASSWORD from docker-compose.misp.yml (sourced from .env.misp), so the
// usual invocation is:
//
//   docker cp setpass.php <misp-core>:/tmp/setpass.php
//   docker exec <misp-core> php /tmp/setpass.php
//
// To set a different password than the one in .env.misp, override explicitly:
//   docker exec -e MISP_ADMIN_PASSWORD="$NEW_PW" <misp-core> php /tmp/setpass.php

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

$dbHost    = getenv('MYSQL_HOST') ?: 'misp-db';
$dbName    = getenv('MYSQL_DATABASE') ?: 'misp';
$dbUser    = getenv('MYSQL_USER') ?: 'misp';
$dbPass    = require_env(['MISP_DB_PASSWORD', 'MYSQL_PASSWORD']);
$adminMail = require_env(['MISP_ADMIN_EMAIL', 'ADMIN_EMAIL']);
$adminPass = require_env(['MISP_ADMIN_PASSWORD', 'ADMIN_PASSWORD']);

$hash = password_hash($adminPass, PASSWORD_BCRYPT);
$pdo = new PDO("mysql:host={$dbHost};dbname={$dbName}", $dbUser, $dbPass);
$stmt = $pdo->prepare("UPDATE users SET password=?, change_pw=0 WHERE email=?");
$stmt->execute([$hash, $adminMail]);

echo "Updated " . $stmt->rowCount() . " row(s) for " . $adminMail . PHP_EOL;
echo "Verify: " . (password_verify($adminPass, $hash) ? 'YES' : 'NO') . PHP_EOL;
