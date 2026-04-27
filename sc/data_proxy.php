<?php
declare(strict_types=1);

header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store, no-cache, must-revalidate, max-age=0');

$config = require __DIR__ . '/config/data_config.php';
$kind = strtolower(trim((string)($_GET['kind'] ?? '')));
$wantMeta = isset($_GET['meta']) || isset($_GET['status']);
$forceRefresh = isset($_GET['refresh']);

if (!isset($config['sources'][$kind])) {
    http_response_code(400);
    echo json_encode(['ok' => false, 'error' => 'kind 必須是 mining 或 crafting'], JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
    exit;
}

$source = $config['sources'][$kind];
$cacheDir = rtrim((string)($config['cache_dir'] ?? (__DIR__ . '/cache')), '/\\');
if (!is_dir($cacheDir)) {
    @mkdir($cacheDir, 0775, true);
}
$cacheFile = $cacheDir . DIRECTORY_SEPARATOR . $source['cache_file'];
$metaFile = $cacheDir . DIRECTORY_SEPARATOR . $source['meta_file'];
$updateInterval = max(60, (int)($config['update_interval_seconds'] ?? 300));
$timeout = max(5, (int)($config['timeout_seconds'] ?? 20));
$userAgent = (string)($config['user_agent'] ?? 'Mozilla/5.0');
$allowStaleCache = (bool)($config['allow_stale_cache'] ?? true);

function read_json_array_file(string $path): array {
    if (!is_file($path)) return [];
    $raw = @file_get_contents($path);
    if ($raw === false || trim($raw) === '') return [];
    $data = json_decode($raw, true);
    return is_array($data) ? $data : [];
}
function write_file_atomic(string $path, string $content): bool {
    $tmp = $path . '.tmp';
    if (@file_put_contents($tmp, $content, LOCK_EX) === false) return false;
    return @rename($tmp, $path);
}
function decode_json_payload(string $payload): ?array {
    $trim = trim($payload);
    if ($trim === '') return null;
    if (strncmp($trim, "\xEF\xBB\xBF", 3) === 0) $trim = substr($trim, 3);
    $data = json_decode($trim, true);
    return json_last_error() === JSON_ERROR_NONE && is_array($data) ? $data : null;
}
function extract_google_file_id(string $value): string {
    $value = trim($value);
    if ($value === '') return '';
    if (preg_match('/^[A-Za-z0-9_-]{20,}$/', $value)) return $value;
    if (preg_match('~[?&]id=([A-Za-z0-9_-]+)~', $value, $m)) return $m[1];
    if (preg_match('~/d/([A-Za-z0-9_-]+)~', $value, $m)) return $m[1];
    return '';
}
function extract_google_resource_key(string $url): string {
    if (preg_match('~[?&]resourcekey=([A-Za-z0-9_-]+)~', $url, $m)) return $m[1];
    return '';
}
function build_google_candidate_urls(string $value): array {
    $value = trim($value);
    if ($value === '') return [];
    $id = extract_google_file_id($value);
    $resourceKey = extract_google_resource_key($value);
    $urls = [];
    if (preg_match('~^https?://~i', $value)) $urls[] = $value;
    if ($id !== '') {
        $suffix = $resourceKey !== '' ? '&resourcekey=' . rawurlencode($resourceKey) : '';
        $urls[] = 'https://drive.google.com/uc?export=download&id=' . rawurlencode($id) . $suffix;
        $urls[] = 'https://drive.google.com/uc?export=download&confirm=t&id=' . rawurlencode($id) . $suffix;
        $urls[] = 'https://drive.usercontent.google.com/download?id=' . rawurlencode($id) . '&export=download&confirm=t' . ($resourceKey !== '' ? '&resourcekey=' . rawurlencode($resourceKey) : '');
        $urls[] = 'https://drive.google.com/file/d/' . rawurlencode($id) . '/view?usp=sharing' . ($resourceKey !== '' ? '&resourcekey=' . rawurlencode($resourceKey) : '');
    }
    return array_values(array_unique(array_filter($urls)));
}
function normalize_google_escape_string(string $value): string {
    $value = str_replace(['\\u003d', '\\u0026', '\\/'], ['=', '&', '/'], $value);
    return html_entity_decode($value, ENT_QUOTES | ENT_HTML5, 'UTF-8');
}
function extract_google_confirm_url(string $html, string $baseUrl = ''): string {
    $patterns = [
        '~href="([^"]*?/uc\?export=download[^"]+)"~i',
        '~"downloadUrl":"([^"]+)"~i',
        '~action="([^"]*?/uc)"[^>]*>.*?name="id" value="([A-Za-z0-9_-]+)".*?name="confirm" value="([^"]+)"~is',
    ];
    foreach ($patterns as $idx => $pattern) {
        if (preg_match($pattern, $html, $m)) {
            if ($idx === 2) {
                return $m[1] . '?export=download&id=' . rawurlencode($m[2]) . '&confirm=' . rawurlencode($m[3]);
            }
            $url = normalize_google_escape_string($m[1]);
            if (strpos($url, '//') === 0) return 'https:' . $url;
            if (strpos($url, '/uc?') === 0) return 'https://drive.google.com' . $url;
            if (!preg_match('~^https?://~i', $url) && $baseUrl !== '') {
                $parts = parse_url($baseUrl);
                if (!empty($parts['scheme']) && !empty($parts['host'])) {
                    return $parts['scheme'] . '://' . $parts['host'] . '/' . ltrim($url, '/');
                }
            }
            return $url;
        }
    }
    return '';
}
function http_fetch(string $url, int $timeout, string $userAgent): array {
    $headers = [];
    if (function_exists('curl_init')) {
        $cookie = tempnam(sys_get_temp_dir(), 'scgd_');
        $ch = curl_init($url);
        curl_setopt_array($ch, [
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_FOLLOWLOCATION => true,
            CURLOPT_MAXREDIRS => 10,
            CURLOPT_CONNECTTIMEOUT => $timeout,
            CURLOPT_TIMEOUT => $timeout,
            CURLOPT_USERAGENT => $userAgent,
            CURLOPT_HTTPHEADER => ['Accept: application/json,text/plain,*/*', 'Cache-Control: no-cache', 'Pragma: no-cache'],
            CURLOPT_SSL_VERIFYPEER => true,
            CURLOPT_SSL_VERIFYHOST => 2,
            CURLOPT_COOKIEJAR => $cookie,
            CURLOPT_COOKIEFILE => $cookie,
            CURLOPT_HEADERFUNCTION => static function ($ch, $line) use (&$headers) {
                $len = strlen($line);
                if (strpos($line, ':') !== false) {
                    [$k, $v] = explode(':', $line, 2);
                    $headers[strtolower(trim($k))] = trim($v);
                }
                return $len;
            },
        ]);
        $body = curl_exec($ch);
        $status = (int) curl_getinfo($ch, CURLINFO_HTTP_CODE);
        $error = curl_error($ch);
        $effectiveUrl = (string) curl_getinfo($ch, CURLINFO_EFFECTIVE_URL);
        curl_close($ch);
        if (is_file($cookie)) @unlink($cookie);
        return ['ok' => is_string($body) && $error === '' && $status >= 200 && $status < 300, 'status' => $status, 'body' => is_string($body) ? $body : '', 'error' => $error, 'headers' => $headers, 'effective_url' => $effectiveUrl];
    }
    if (!ini_get('allow_url_fopen')) {
        return ['ok' => false, 'status' => 0, 'body' => '', 'error' => '伺服器未開啟 cURL，也未開啟 allow_url_fopen', 'headers' => [], 'effective_url' => $url];
    }
    $context = stream_context_create([
        'http' => ['method' => 'GET', 'timeout' => $timeout, 'ignore_errors' => true, 'header' => "User-Agent: {$userAgent}\r\nAccept: application/json,text/plain,*/*\r\nCache-Control: no-cache\r\nPragma: no-cache\r\n"],
        'ssl' => ['verify_peer' => true, 'verify_peer_name' => true],
    ]);
    $body = @file_get_contents($url, false, $context);
    $status = 0;
    foreach (($http_response_header ?? []) as $line) {
        if (preg_match('~HTTP/\S+\s+(\d+)~', $line, $m)) $status = (int) $m[1];
        elseif (strpos($line, ':') !== false) { [$k, $v] = explode(':', $line, 2); $headers[strtolower(trim($k))] = trim($v); }
    }
    return ['ok' => is_string($body) && $status >= 200 && $status < 300, 'status' => $status, 'body' => is_string($body) ? $body : '', 'error' => is_string($body) ? '' : 'file_get_contents 讀取失敗', 'headers' => $headers, 'effective_url' => $url];
}
function fetch_google_json(string $sourceValue, int $timeout, string $userAgent): array {
    $lastError = '';
    foreach (build_google_candidate_urls($sourceValue) as $candidateUrl) {
        $res = http_fetch($candidateUrl, $timeout, $userAgent);
        if (!$res['ok']) {
            $lastError = $res['error'] !== '' ? $res['error'] : ('HTTP ' . $res['status']);
            continue;
        }
        $data = decode_json_payload($res['body']);
        if (is_array($data)) {
            return ['ok' => true, 'body' => $res['body'], 'json' => $data, 'headers' => $res['headers'], 'status' => $res['status'], 'source_url' => $res['effective_url'] ?: $candidateUrl, 'error' => ''];
        }
        $confirmUrl = extract_google_confirm_url($res['body'], $res['effective_url'] ?: $candidateUrl);
        if ($confirmUrl !== '') {
            $res2 = http_fetch($confirmUrl, $timeout, $userAgent);
            if ($res2['ok']) {
                $data2 = decode_json_payload($res2['body']);
                if (is_array($data2)) {
                    return ['ok' => true, 'body' => $res2['body'], 'json' => $data2, 'headers' => $res2['headers'], 'status' => $res2['status'], 'source_url' => $res2['effective_url'] ?: $confirmUrl, 'error' => ''];
                }
                $lastError = 'Google Drive 返回的是下載確認頁，仍未取得 JSON';
                continue;
            }
            $lastError = $res2['error'] !== '' ? $res2['error'] : ('HTTP ' . $res2['status']);
            continue;
        }
        if (stripos($res['body'], '<html') !== false || stripos($res['body'], '<!doctype html') !== false) $lastError = 'Google Drive 返回 HTML 頁面，請確認檔案已公開，或連結不是資料預覽頁';
        else $lastError = '遠端內容不是合法 JSON';
    }
    return ['ok' => false, 'body' => '', 'json' => null, 'headers' => [], 'status' => 0, 'source_url' => '', 'error' => $lastError !== '' ? $lastError : '無法從 Google Drive 取得 JSON'];
}

$meta = read_json_array_file($metaFile);
$cachedBody = is_file($cacheFile) ? @file_get_contents($cacheFile) : false;
$cachedData = is_string($cachedBody) ? decode_json_payload($cachedBody) : null;
$now = time();
$needRefresh = $forceRefresh || !is_array($cachedData) || (($now - (int)($meta['last_check'] ?? 0)) >= $updateInterval);
$state = 'cache';
$message = '已使用本機快取';
$servedData = $cachedData;
$remoteValue = trim((string)($source['url'] ?? ''));
$lastError = '';

if ($needRefresh && $remoteValue !== '') {
    $remote = fetch_google_json($remoteValue, $timeout, $userAgent);
    if ($remote['ok']) {
        $newHash = sha1($remote['body']);
        $oldHash = (string)($meta['hash'] ?? '');
        $changed = ($newHash !== $oldHash) || !is_file($cacheFile);
        if ($changed) { write_file_atomic($cacheFile, $remote['body']); $meta['last_update'] = $now; }
        $meta['last_check'] = $now;
        $meta['hash'] = $newHash;
        $meta['http_status'] = $remote['status'];
        $meta['source_url'] = $remote['source_url'];
        $meta['etag'] = $remote['headers']['etag'] ?? ($meta['etag'] ?? '');
        $meta['last_modified'] = $remote['headers']['last-modified'] ?? ($meta['last_modified'] ?? '');
        write_file_atomic($metaFile, json_encode($meta, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES | JSON_PRETTY_PRINT));
        $servedData = $remote['json'];
        $state = $changed ? 'remote_updated' : 'remote_same';
        $message = $changed ? '已從 Google Drive 更新快取' : 'Google Drive 資料無變更';
    } else {
        $lastError = $remote['error'];
        $meta['last_check'] = $now;
        $meta['last_error'] = $lastError;
        write_file_atomic($metaFile, json_encode($meta, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES | JSON_PRETTY_PRINT));
    }
} elseif ($remoteValue === '') {
    $message = '尚未設定 Google Drive 連結，使用本機快取';
}

if (!is_array($servedData) && $allowStaleCache && is_array($cachedData)) {
    $servedData = $cachedData;
    $state = 'stale_cache';
    $message = $lastError !== '' ? ('遠端失敗，改用舊快取：' . $lastError) : '遠端失敗，改用舊快取';
}
if (!is_array($servedData)) {
    http_response_code(500);
    echo json_encode(['ok' => false, 'error' => $lastError !== '' ? $lastError : '無法取得資料', 'kind' => $kind, 'hint' => '請確認 Google Drive 檔案設為任何知道連結的人可檢視，且 config/data_config.php 的 url 是正確連結或 FILE_ID。', 'cache_exists' => is_file($cacheFile)], JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES | JSON_PRETTY_PRINT);
    exit;
}
header('X-SC-State: ' . $state);
header('X-SC-Message: ' . rawurlencode($message));
header('X-SC-Last-Check: ' . (string)($meta['last_check'] ?? 0));
header('X-SC-Last-Update: ' . (string)($meta['last_update'] ?? 0));
header('X-SC-Source-Url: ' . rawurlencode((string)($meta['source_url'] ?? $remoteValue)));
$responseMeta = [
    'kind' => $kind,
    'state' => $state,
    'message' => $message,
    'last_check' => (int)($meta['last_check'] ?? 0),
    'last_update' => (int)($meta['last_update'] ?? 0),
    'source_url' => (string)($meta['source_url'] ?? $remoteValue),
    'cache_file' => basename($cacheFile),
];
if ($wantMeta) {
    echo json_encode(['ok' => true] + $responseMeta, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES | JSON_PRETTY_PRINT);
    exit;
}
echo json_encode(['ok' => true, 'data' => $servedData, 'meta' => $responseMeta], JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
