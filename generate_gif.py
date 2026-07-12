import cairosvg
from PIL import Image
import io

# Создаём кадры анимации
frames = []
for i in range(20):  # 20 кадров
    # Создаём SVG с разными позициями колосьев
    svg_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 200" width="800" height="200">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#0f0f1a"/>
      <stop offset="100%" stop-color="#1a1a2e"/>
    </linearGradient>
    <linearGradient id="gold-grad" x1="0" y1="1" x2="0.5" y2="0">
      <stop offset="0%" stop-color="#b8860b"/>
      <stop offset="40%" stop-color="#d4a017"/>
      <stop offset="80%" stop-color="#f5d76e"/>
      <stop offset="100%" stop-color="#fff4b8"/>
    </linearGradient>
    <linearGradient id="gold-grad2" x1="0" y1="1" x2="0.5" y2="0">
      <stop offset="0%" stop-color="#a0750a"/>
      <stop offset="50%" stop-color="#c8951e"/>
      <stop offset="100%" stop-color="#e6c44d"/>
    </linearGradient>
    <linearGradient id="stem-grad" x1="0" y1="1" x2="0.5" y2="0">
      <stop offset="0%" stop-color="#4a3e1a"/>
      <stop offset="100%" stop-color="#7a6a2a"/>
    </linearGradient>
    <filter id="glow">
      <feGaussianBlur stdDeviation="2" result="blur"/>
      <feMerge>
        <feMergeNode in="blur"/>
        <feMergeNode in="SourceGraphic"/>
      </feMerge>
    </filter>
  </defs>

  <rect width="800" height="200" rx="20" fill="url(#bg)"/>
  <ellipse cx="400" cy="100" rx="350" ry="80" fill="#d4a017" opacity="0.03"/>

  <!-- Стог -->
  <g transform="translate(100, 120)">
    <path d="M 0 40 Q 20 30, 40 40 Q 60 50, 80 40 Q 100 30, 120 40 L 120 50 Q 100 40, 80 50 Q 60 60, 40 50 Q 20 40, 0 50 Z" fill="#d4a017" opacity="0.7"/>
    <path d="M 10 30 Q 30 20, 50 30 Q 70 40, 90 30 Q 110 20, 130 30 L 130 40 Q 110 30, 90 40 Q 70 50, 50 40 Q 30 30, 10 40 Z" fill="#e6c44d" opacity="0.8"/>
    <path d="M 20 20 Q 40 10, 60 20 Q 80 30, 100 20 Q 120 10, 140 20 L 140 30 Q 120 20, 100 30 Q 80 40, 60 30 Q 40 20, 20 30 Z" fill="#fff4b8" opacity="0.9"/>
  </g>

  <!-- Колосья падают -->
  <g transform="translate(60, {20 + i * 2})" filter="url(#glow)">
    <path d="M 35 150 Q 33 100, 36 50 Q 37 30, 36 20" stroke="url(#stem-grad)" stroke-width="3" fill="none" stroke-linecap="round"/>
    <ellipse cx="36" cy="18" rx="5" ry="7" fill="url(#gold-grad)" transform="rotate(-5 36 18)"/>
  </g>
  <g transform="translate(110, {20 + i * 2.5})" filter="url(#glow)">
    <path d="M 85 150 Q 87 100, 84 50 Q 83 30, 84 20" stroke="url(#stem-grad)" stroke-width="3" fill="none" stroke-linecap="round"/>
    <ellipse cx="84" cy="18" rx="5" ry="7" fill="url(#gold-grad)" transform="rotate(5 84 18)"/>
  </g>
  <g transform="translate(85, {10 + i * 3})" filter="url(#glow)">
    <path d="M 60 150 Q 58 90, 61 40 Q 62 20, 61 10" stroke="url(#stem-grad)" stroke-width="3.5" fill="none" stroke-linecap="round"/>
    <ellipse cx="61" cy="8" rx="5.5" ry="8" fill="url(#gold-grad)"/>
  </g>

  <!-- Буквы -->
  <g transform="translate(250, 48)">
    <path d="M 0 24 L 0 0 L 8 0 L 8 24" stroke="#f5d76e" stroke-width="3" fill="none" stroke-linecap="round"/>
    <path d="M 20 24 L 20 0 L 28 0 L 28 24" stroke="#f5d76e" stroke-width="3" fill="none" stroke-linecap="round"/>
    <path d="M 0 12 L 28 12" stroke="#f5d76e" stroke-width="2" fill="none" stroke-linecap="round"/>
    <path d="M 38 24 L 46 6 L 54 24" stroke="#f5d76e" stroke-width="3" fill="none" stroke-linecap="round" stroke-linejoin="round"/>
    <path d="M 42 16 L 50 16" stroke="#f5d76e" stroke-width="2" fill="none" stroke-linecap="round"/>
    <path d="M 62 24 L 62 0 L 74 0 L 74 12 L 62 12 L 74 24" stroke="#f5d76e" stroke-width="3" fill="none" stroke-linecap="round" stroke-linejoin="round"/>
    <path d="M 84 0 L 92 24 L 100 0" stroke="#f5d76e" stroke-width="3" fill="none" stroke-linecap="round" stroke-linejoin="round"/>
    <path d="M 110 0 L 110 24 L 130 24 M 110 12 L 126 12 M 110 0 L 130 0" stroke="#f5d76e" stroke-width="3" fill="none" stroke-linecap="round"/>
    <path d="M 140 8 Q 142 4, 148 4 Q 154 4, 156 10 Q 156 15, 150 17 Q 138 20, 138 28 Q 138 34, 144 36 Q 150 36, 154 32" stroke="#f5d76e" stroke-width="3" fill="none" stroke-linecap="round"/>
    <path d="M 164 0 L 184 0 M 174 0 L 174 24" stroke="#f5d76e" stroke-width="3" fill="none" stroke-linecap="round"/>
    <text x="48" y="54" font-family="'SF Mono', 'Cascadia Code', 'JetBrains Mono', monospace" font-size="12" font-weight="400" letter-spacing="3" fill="#a08030" opacity="0.7">WEB COLLECTION ENGINE</text>
  </g>

  <line x1="40" y1="180" x2="760" y2="180" stroke="url(#gold-grad)" stroke-width="1.5" opacity="0.25"/>
  <line x1="40" y1="182" x2="760" y2="182" stroke="url(#gold-grad)" stroke-width="0.5" opacity="0.1"/>
</svg>"""

    # SVG → PNG через cairosvg
    png_bytes = cairosvg.svg2png(bytestring=svg_content.encode("utf-8"))
    img = Image.open(io.BytesIO(png_bytes))
    frames.append(img)

# Сохраняем GIF
frames[0].save(
    "/home/dima/harvest/logo.gif",
    save_all=True,
    append_images=frames[1:],
    duration=100,  # 100ms на кадр
    loop=0,  # бесконечная анимация
    disposal=2,  # восстанавливать фон
)

print("GIF saved: /home/dima/harvest/logo.gif")
