<?php
$hash = password_hash('LoveBella1000!', PASSWORD_BCRYPT);
$pdo = new PDO('mysql:host=misp-db;dbname=misp', 'misp', '76fd7f85e8717b788ec1af56dc5dd0ec256349e56bbca8d0');
$stmt = $pdo->prepare("UPDATE users SET password=?, change_pw=0 WHERE email='admin@misp.local'");
$stmt->execute([$hash]);
echo "Updated. Hash: " . $hash . PHP_EOL;
echo "Verify: " . (password_verify('LoveBella1000!', $hash) ? 'YES' : 'NO') . PHP_EOL;
