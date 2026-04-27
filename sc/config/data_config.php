<?php
declare(strict_types=1);
return [
    'update_interval_seconds' => 300,
    'timeout_seconds' => 35,
    'user_agent' => 'Mozilla/5.0 SC-Mobile-Web/4.0 PHP-GDrive-JSON',
    'cache_dir' => __DIR__ . '/../cache',
    'allow_stale_cache' => true,
    'sources' => [
        'mining' => [
            'label' => 'Mining JSON',
            'url' => 'https://drive.google.com/uc?export=download&id=1t9L3RSl1gPQRrsltH58uBySzC4_pxWjt',
            'cache_file' => 'mining.json',
            'meta_file' => 'mining.meta.json',
        ],
        'crafting' => [
            'label' => 'Crafting JSON',
            'url' => 'https://drive.google.com/uc?export=download&id=1-nxq45uudEsGzV7IZxddUOeOT0m4b6hx',
            'cache_file' => 'crafting.json',
            'meta_file' => 'crafting.meta.json',
        ],
    ],
];
