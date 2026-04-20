<?php
$pdo = new PDO('mysql:host=misp-db;dbname=misp', 'misp', '76fd7f85e8717b788ec1af56dc5dd0ec256349e56bbca8d0');

$authkey = bin2hex(random_bytes(20));
$hashed  = password_hash($authkey, PASSWORD_BCRYPT);

$stmt = $pdo->prepare("INSERT INTO auth_keys (uuid, authkey, authkey_start, authkey_end, user_id, created, expiration, read_only, allowed_ips, comment) VALUES (UUID(), ?, ?, ?, 1, UNIX_TIMESTAMP(), 0, 0, NULL, 'SOC Brain auto-generated')");
$stmt->execute([$hashed, substr($authkey, 0, 4), substr($authkey, -4)]);

echo "API Key (save this): " . $authkey . PHP_EOL;
