"""Real product photos from Wikimedia Commons (freely licensed, credited on the product page).

product name -> (Commons file title, exact model?)
`exact=False` means the photo shows a closely related model (same family and design); the
product page says so. Products not listed keep their generated illustration.
`python manage.py fetch_product_photos` downloads them; `seed` runs it automatically.
"""

PHOTOS = {
    "ASUS Vivobook 15 (X1504VA)": ("File:Asus vivobook S15 i9.jpg", False),
    "Lenovo Legion 5i": ("File:Lenovo Legion Y520 (1).jpg", False),
    "Acer Nitro V 15": ("File:Acer Nitro V 15 2026-08-15 gaming laptop 02.jpg", True),
    "Microsoft Surface Pro 11": ("File:Surface Pro 9 in Sapphire colour.jpg", False),
    "HP Envy x360 14": ("File:HP Envy x360-15.jpg", False),
    "Lenovo Yoga 7i 14": ("File:Lenovo Yoga 3 Pro hybrid-laptop in tent mode.jpg", False),
    "Apple MacBook Air 13\" (M2)": ("File:M2 Macbook Air Starlight model.jpg", True),
    "Apple MacBook Air 15\" (M3)": ("File:MacBook Air (15-inch, M4, Silver).jpg", False),
    "Apple MacBook Pro 16\" (M4 Pro)": ("File:MacBook Pro (16-inch, M4 Pro, Silver).jpg", True),
    "AMD Ryzen 5 7600": ("File:AMD Ryzen 5 7600 top IMGP6773 smial wp.jpg", True),
    "AMD Ryzen 7 7800X3D": ("File:Ryzen 7 7800 X3D, unlocked.jpg", True),
    "Intel Core i5-14400F": ("File:Intel Core i5 13600K.jpg", False),
    "Corsair Vengeance 32GB (2×16GB) DDR5-6000": ("File:2023 Pamięci Corsair Vengeance RGB.jpg", False),
    "Samsung 990 PRO 1TB NVMe SSD": ("File:Samsung MZ-V9P4T0 (Samsung 990 PRO 4TB) 20250226 002.png", True),
    "Seagate BarraCuda 2TB Hard Drive": ("File:Seagate BarraCuda Compute 2TB 3.5-inch SATA HDD - top view.jpg", True),
    "Corsair 4000D Airflow": ("File:Corsair 4000D Airflow mid-tower ATX case.tif", True),
    "Keychron K2 Pro Wireless Mechanical Keyboard": ("File:Keychron K4 mechanical keyboard.jpg", False),
    "Logitech MX Keys S Wireless Keyboard": ("File:Logitech MX Keys YR0073 Wireless Keyboard.jpg", False),
    "Razer BlackWidow V4 X Tenkeyless": ("File:Razer BlackWidow Ultimate 2014 Elite Mechanical Gaming Keyboard.jpg", False),
    "Logitech Lift Vertical Ergonomic Mouse": ("File:Logitech MX Vertical Ergonomic Mouse.jpg", False),
    "Microsoft Arc Mouse": ("File:MS-Arc-Mouse.jpg", True),
    "Audio-Technica ATH-M50x Studio Headphones": ("File:Audio Technica ATH-M50 Headphones.jpg", False),
    "Apple AirPods 4": ("File:AirPods (cropped).jpg", False),
    "Logitech C920s Pro HD Webcam": ("File:Webcam 01.jpg", False),
    "Logitech StreamCam": ("File:Logicool StreamCam (cropped).jpg", True),
    "Logitech C270 HD Webcam": ("File:Webcam on computer screen.jpg", True),
}
