import os
from flask import Flask

base_dir = os.path.abspath(os.path.dirname(__file__))
app = Flask(__name__, static_folder=os.path.join(base_dir, 'static'))

# ====================== СТИЛҲО ======================
CSS = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@900&family=Montserrat:wght@400;700;800&display=swap');
    :root { --red: #ff0000; --dark-red: #b30000; --dark: #1a1a1a; }
    * { margin: 0; padding: 0; box-sizing: border-box; font-family: 'Montserrat', sans-serif; }
    body { background: #ffffff; overflow-x: hidden; color: var(--dark); }

    header { 
        background: linear-gradient(135deg, var(--red) 0%, var(--dark-red) 100%);
        height: 60vh; display: flex; flex-direction: column; justify-content: center;
        align-items: center; position: relative; color: white;
        clip-path: polygon(0 0, 100% 0, 100% 90%, 0 100%); text-align: center;
    }

    @keyframes float {
        0%, 100% { transform: translateY(0px); }
        50% { transform: translateY(-15px); }
    }

    .tfc-title {
        font-family: 'Poppins', sans-serif; font-size: clamp(5rem, 15vw, 10rem);
        font-weight: 900; display: flex; gap: 5px; animation: float 4s ease-in-out infinite;
    }

    .tfc-title span { display: inline-block; animation: bounceIn 0.8s cubic-bezier(0.175, 0.885, 0.32, 1.275) forwards; opacity: 0; }
    .tfc-title span:nth-child(1) { animation-delay: 0.1s; }
    .tfc-title span:nth-child(2) { animation-delay: 0.3s; }
    .tfc-title span:nth-child(3) { animation-delay: 0.5s; }

    @keyframes bounceIn { from { opacity: 0; transform: translateY(-100px); } to { opacity: 1; transform: translateY(0); } }

    nav { 
        background: white; padding: 15px; display: flex; justify-content: center;
        position: sticky; top: 0; z-index: 1000; box-shadow: 0 2px 10px rgba(0,0,0,0.05);
    }
    nav a { color: #333; font-weight: 700; text-decoration: none; margin: 0 15px; text-transform: uppercase; font-size: 0.8rem; }

    .section-title { text-align: center; font-size: clamp(2rem, 8vw, 3.5rem); color: var(--red); margin: 40px 0; font-weight: 900; }
    .container { max-width: 1200px; margin: 0 auto 60px; padding: 0 20px; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 25px; }

    .card { 
        background: white; border-radius: 30px; padding: 20px; text-align: center;
        border: 1px solid #eee; position: relative; cursor: pointer;
        transition: 0.4s; text-decoration: none; color: inherit; outline: none; overflow: hidden;
    }

    .food-img { 
        width: 100%; height: 180px; border-radius: 20px; object-fit: cover; 
        margin-bottom: 15px; background: #f0f0f0;
    }

    .continue-btn {
        background: var(--red); color: white; padding: 12px; border-radius: 50px;
        font-weight: bold; margin-top: 10px; display: inline-block;
        opacity: 0; transform: translateY(20px); transition: 0.4s; width: 100%;
    }

    .card:focus .continue-btn, .card:active .continue-btn { 
        opacity: 1; transform: translateY(0); 
    }
    .card:focus { 
        border-color: var(--red); transform: translateY(-5px); 
        box-shadow: 0 10px 20px rgba(0,0,0,0.1); 
    }

    .price-tag { font-size: 1.6rem; color: var(--red); font-weight: 900; margin: 5px 0; }
    .menu-cat { margin: 40px 0 20px; border-left: 6px solid red; padding-left: 15px; text-align: left; font-size: 1.5rem; text-transform: uppercase; }
    .back-btn { display: inline-block; margin: 20px 0; padding: 12px 30px; background: var(--red); color: white; border-radius: 50px; text-decoration: none; font-weight: bold; }
</style>
"""

def get_header():
    return """
    <header>
        <div class="tfc-title"><span>T</span><span>F</span><span>C</span></div>
        <div style="letter-spacing:5px; font-weight:700; font-size:1.8rem;">KULOB CITY</div>
    </header>
    <nav>
        <a href="/">АСОСӢ</a>
        <a href="/fastfood">FastFood</a>
        <a href="/sushi">СУШИ</a>
        <a href="/pizza">ПИТСА</a>
    </nav>
    """

@app.route('/')
def home():
    return CSS + get_header() + """
    <h2 class="section-title">БАХШҲО</h2>
    <div class="container">
        <div class="grid">
            <div class="card" tabindex="0">
                <img src="/static/nondog.png" class="food-img" onerror="this.src='https://via.placeholder.com/400x180/ff0000/ffffff?text=ФАСТФУД'">
                <h3>ФАСТФУД</h4>
                <a href="/fastfood" class="continue-btn">ДАВОМ →</a>
            </div>
            <div class="card" tabindex="0">
                <img src="https://images.unsplash.com/photo-1579871494447-9811cf80d66c?w=400" class="food-img">
                <h3>СУШИ</h3>
                <a href="/sushi" class="continue-btn">ДАВОМ →</a>
            </div>
            <div class="card" tabindex="0">
                <img src="https://images.unsplash.com/photo-1513104890138-7c749659a591?w=400" class="food-img">
                <h3>ПИТСА</h3>
                <a href="/pizza" class="continue-btn">ДАВОМ →</a>
            </div>
        </div>
    </div>
    """

@app.route('/fastfood')
def fastfood():
    menu = {
        "🌭 ХОТ-ДОГҲО": [
            ("Нон-Дог", "5/7c", "1.png"),
            ("Булочка", "6/8c", "2.png"),
            ("М-Дог", "10c", "3.png"),
            ("TFC-Дог", "18/30c", "4.png"),
            ("Чикен-Дог", "12/24c", "5.png"),
            ("Начо-Дог", "14/26c", "6.png"),
            ("Чикенчиз-Дог", "16/28c", "7.png"),
            ("Шеф-Дог", "17/29c", "8.png"),
            ("Американо-Дог", "16/25c", "9.png"),
            ("Итали-Дог", "12/20c", "10.png"),
            ("Биф-Дог", "41c", "11.png"),
        ],
        "🍔 БУРГЕРҲО ВА СЭНДВИЧҲО": [
            ("Классик Бургер", "23c", "12.png"),
            ("Классик Чизбургер", "27c", "13.png"),
            ("Дабл Чизбургер", "43c", "14.png"),
            ("Дабл Бургер", "37c", "15.png"),
            ("TFC Бургер", "48c", "16.png"),
            ("Шеф Бургер", "51c", "17.png"),
            ("Сэндвич Simple", "19c", "18.png"),
            ("Сэндвич бо панир", "23c", "19.png"),
            ("Панини бо мурғ", "26c", "20.png"),
            ("Панини бо гӯшти гов", "43c", "21.png"),
        ],
        "🌯 ТОРТИЛЯҲО": [
            ("Тортиля бо мурғ ва панир", "23c", "22.png"),
            ("Тортиля бо мурғ", "15c", "23.png"),
            ("Тортиля Микс", "26c", "24.png"),
            ("Тортиля TFC", "40c", "25.png"),
            ("Тортиля бо гӯшти гов", "32c", "26.png"),
            ("Тортиля дар темпура", "28c", "27.png"),
        ],
        "🍟 ГАРНИРҲО ВА МАҲСУЛОТИ МУРҒӢ": [
            ("Картошка фри", "12/17c", "28.png"),
            ("Картошкаи деҳотӣ", "13/18c", "29.png"),
            ("Шарикҳои картошкагӣ", "14/19c", "30.png"),
            ("Наггетсҳо", "17/27c", "31.png"),
            ("Кӯлчаҳои тунд", "35/45c", "32.png"),
            ("Кӯлчаҳои ширин", "36/46c", "33.png"),
            ("Почаҳои мурғ", "69/109c", "34.png"),
            ("Сырные палочки", "28c", "35.png"),
            ("Баскет", "130c", "36.png"),
        ]
    }
    
    content = CSS + get_header() + '<h2 class="section-title">🍔 МЕНЮ ФАСТФУД</h2><div class="container">'
    
    for cat, items in menu.items():
        content += f'<h3 class="menu-cat">{cat}</h3><div class="grid">'
        for name, price, file in items:
            content += f"""
            <div class="card" tabindex="0">
                <img src="/static/{file}" class="food-img" 
                     onerror="this.src='https://via.placeholder.com/400x180/ff0000/ffffff?text={name.replace(' ', '+')}'">
                <h3>{name}</h3>
                <div class="price-tag">{price}</div>
                <div class="continue-btn">ИНТИХОБ КАРДАН</div>
            </div>"""
        content += '</div>'
    
    content += '<center><a href="/" class="back-btn">← БА АСОСӢ</a></center></div>'
    return content


@app.route('/sushi')
def sushi():
    return CSS + get_header() + """
    <h2 class="section-title">🍣 СУШИ</h2>
    <div class="container" style="text-align:center; padding:100px 20px;">
        <h3>Дар ҳоли омодашавӣ...</h3>
        <center><a href="/" class="back-btn">← БА АСОСӢ</a></center>
    </div>
    """

@app.route('/pizza')
def pizza():
    return CSS + get_header() + """
    <h2 class="section-title">🍕 ПИТСА</h2>
    <div class="container" style="text-align:center; padding:100px 20px;">
        <h3>Дар ҳоли омодашавӣ...</h3>
        <center><a href="/" class="back-btn">← БА АСОСӢ</a></center>
    </div>
    """


if __name__ == '__main__':
    print("Сервер оғоз шуд! Браузерро кушо ва ба http://127.0.0.1:5000 рав.")
    app.run(host='0.0.0.0', port=5000, debug=True)