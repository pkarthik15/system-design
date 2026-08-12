# bench.ps1
$base = "http://localhost:8000"
$heavy = 2796
$light = 50        # replace with your light user

$urls = @{
    "list p1 heavy"   = "$base/bookmarks?user_id=$heavy&page=1"
    "list p500 heavy" = "$base/bookmarks?user_id=$heavy&page=500"
    "list p1 light"   = "$base/bookmarks?user_id=$light&page=1"
    "tag python"      = "$base/bookmarks?user_id=$heavy&tag=python"
    "search python"   = "$base/bookmarks/search?user_id=$heavy&q=python"
    "search zeppelin" = "$base/bookmarks/search?user_id=$heavy&q=zeppelin"
}

foreach ($name in $urls.Keys) {
    curl.exe -s $urls[$name] | Out-Null          # warmup, discarded
    $times = 1..5 | ForEach-Object {
        (Measure-Command { curl.exe -s $urls[$name] }).TotalMilliseconds
    }
    $median = ($times | Sort-Object)[2]
    "{0,-18} {1,8:N1} ms" -f $name, $median
}