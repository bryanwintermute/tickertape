#!/bin/bash
curl -s -H "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36" "https://fonts.googleapis.com/css2?family=Outfit:wght@400;600;700&display=swap" > outfit.css
for url in $(grep -o 'https://[^)]*\.woff2' outfit.css); do
    filename=$(basename "$url")
    wget -q -O "$filename" "$url"
    sed -i "s|$url|fonts/$filename|g" outfit.css
done
