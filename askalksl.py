from flask import Flask, render_template_string

app = Flask(__name__)

# Шаблони мукаммал ва бисёр зебо бо технологияи WebGL
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="tg">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TFC Cinematic Logo</title>
    <style>
        body {
            margin: 0;
            padding: 0;
            overflow: hidden;
            background-color: #f7f9fa; /* Ранги заминаи сафеди мулоим */
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        }
        #canvas-container {
            width: 100vw;
            height: 100vh;
            display: block;
        }
        /* Тугмаи бисёр зебо ва минималистӣ */
        #replay-btn {
            position: absolute;
            bottom: 40px;
            left: 50%;
            transform: translateX(-50%);
            padding: 14px 28px;
            background: rgba(10, 34, 64, 0.9);
            color: #ffffff;
            border: none;
            border-radius: 30px; /* Думалони зебо */
            cursor: pointer;
            font-weight: 500;
            font-size: 12px;
            letter-spacing: 3px;
            text-transform: uppercase;
            backdrop-filter: blur(10px);
            transition: all 0.4s cubic-bezier(0.16, 1, 0.3, 1);
            box-shadow: 0 10px 30px rgba(10, 34, 64, 0.15);
        }
        #replay-btn:hover {
            background: #0A2240;
            transform: translateX(-50%) translateY(-3px);
            box-shadow: 0 15px 35px rgba(10, 34, 64, 0.25);
        }
        #replay-btn:active {
            transform: translateX(-50%) translateY(0) scale(0.95);
        }
    </style>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script> 
    <script src="https://unpkg.com/three@0.128.0/examples/js/postprocessing/EffectComposer.js"></script>
    <script src="https://unpkg.com/three@0.128.0/examples/js/postprocessing/RenderPass.js"></script>
    <script src="https://unpkg.com/three@0.128.0/examples/js/postprocessing/UnrealBloomPass.js"></script>
    <script src="https://unpkg.com/three@0.128.0/examples/js/loaders/FontLoader.js"></script>
    <script src="https://unpkg.com/three@0.128.0/examples/js/geometries/TextGeometry.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/gsap/3.12.2/gsap.min.js"></script>
</head>
<body>

    <div id="canvas-container"></div>
    <button id="replay-btn">Пайваст КУН (Replay)</button>

    <script>
        // --- 1. ТАШКИЛИ СЕХНАИ 3D ---
        const container = document.getElementById('canvas-container');
        const scene = new THREE.Scene();
        scene.background = new THREE.Color(0x050505); // Заминаи торик барои эффекти Bloom

        const camera = new THREE.PerspectiveCamera(40, window.innerWidth / window.innerHeight, 0.1, 100);
        camera.position.set(0, 0, 11);

        const renderer = new THREE.WebGLRenderer({ antialias: true });
        renderer.setSize(window.innerWidth, window.innerHeight);
        renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
        renderer.shadowMap.enabled = true;
        renderer.shadowMap.type = THREE.PCFSoftShadowMap; // Сояҳои ниҳоят мулоим
        renderer.toneMapping = THREE.ACESFilmicToneMapping; // Рангҳои синамоӣ
        renderer.toneMappingExposure = 1.2;
        container.appendChild(renderer.domElement);

        // --- Post-processing (Bloom Effect) ---
        const composer = new EffectComposer(renderer);
        const renderPass = new RenderPass(scene, camera);
        composer.addPass(renderPass);
        const bloomPass = new UnrealBloomPass(new THREE.Vector2(window.innerWidth, window.innerHeight), 1.5, 0.4, 0.85); // strength, radius, threshold
        bloomPass.threshold = 0.1;
        composer.addPass(bloomPass);

        // --- 2. НУРҲОИ СИНАМОӢ (Studio Lighting) ---
        const ambientLight = new THREE.AmbientLight(0xffffff, 0.6);
        scene.add(ambientLight);

        // Нури асосии дурахшон бо сояҳои зебо
        const mainLight = new THREE.DirectionalLight(0xffffff, 1.2);
        mainLight.position.set(5, 10, 8);
        mainLight.castShadow = true;
        mainLight.shadow.mapSize.width = 2048;
        mainLight.shadow.mapSize.height = 2048;
        mainLight.shadow.bias = -0.001;
        scene.add(mainLight);

        // Нури иловагӣ (Fill Light)
        const fillLight = new THREE.DirectionalLight(0xffaa00, 0.5); // Ранги каме гарм
        fillLight.position.set(-5, 5, 5);
        scene.add(fillLight);

        // Нури пушти саҳна (Back Light)
        const backLight = new THREE.DirectionalLight(0x00aaff, 0.3); // Ранги кабуд
        backLight.position.set(0, -5, -10);
        scene.add(rimLight);
        // Нури паҳлӯӣ барои дурахши канори ҷисмҳо (Rim Light)
        const rimLight = new THREE.DirectionalLight(0xb1d4ff, 0.6);
        rimLight.position.set(-8, -4, 5);
        scene.add(rimLight);

        // --- 3. СОХТАНИ ШАКЛҲОИ ЗЕБОИ "TFC" ---
        // Маводи премиум - Кабуди дурахшон бо эффекти лак ва металл
        const premiumMaterial = new THREE.MeshPhysicalMaterial({
            color: 0x071D3A, 
            roughness: 0.1,
            metalness: 0.9,
            clearcoat: 1.0,
            clearcoatRoughness: 0.05,
            sheen: 1.0,
            sheenRoughness: 0.1,
            sheenColor: 0x00aaff
        });

        const extrudeSettings = { 
            depth: 0.35, 
            bevelEnabled: true, 
            bevelSegments: 8, 
            steps: 1, 
            bevelSize: 0.04, 
            bevelThickness: 0.04 
        };

        // Шакли 1: Қисми чап (T)
        const shapeT = new THREE.Shape();
        shapeT.moveTo(-1.6, 1.5);
        shapeT.lineTo(-0.7, 1.5);
        shapeT.lineTo(-0.7, -1.5);
        shapeT.lineTo(-1.2, -1.5);
        shapeT.lineTo(-1.2, 0.9);
        shapeT.lineTo(-1.6, 0.9);
        const geomT = new THREE.ExtrudeGeometry(shapeT, extrudeSettings);
        const meshT = new THREE.Mesh(geomT, premiumMaterial);
        meshT.castShadow = true;
        meshT.receiveShadow = true;
        
        // Шакли 2: Қисми мобайн (F)
        const shapeF = new THREE.Shape();
        shapeF.moveTo(-0.4, 0.8);
        shapeF.lineTo(0.5, 0.8);
        shapeF.lineTo(0.5, 0.4);
        shapeF.lineTo(-0.4, 0.4);
        shapeF.lineTo(-0.4, 0.0);
        shapeF.lineTo(0.2, 0.0);
        shapeF.lineTo(0.2, -0.4);
        shapeF.lineTo(-0.4, -0.4);
        const geomF = new THREE.ExtrudeGeometry(shapeF, extrudeSettings);
        const meshF = new THREE.Mesh(geomF, premiumMaterial);
        meshF.castShadow = true;
        meshF.receiveShadow = true;

        // Шакли 3: Қисми рост (C)
        const shapeC = new THREE.Shape();
        shapeC.moveTo(1.6, 1.2);
        shapeC.lineTo(0.8, 1.2);
        shapeC.quadraticCurveTo(0.5, 0.8, 0.5, 0);
        shapeC.quadraticCurveTo(0.5, -0.8, 0.8, -1.2);
        shapeC.lineTo(1.6, -1.2);
        shapeC.lineTo(1.6, -0.7);
        shapeC.lineTo(1.1, -0.7);
        shapeC.quadraticCurveTo(0.9, -0.5, 0.9, 0);
        shapeC.quadraticCurveTo(0.9, 0.5, 1.1, 0.7);
        shapeC.lineTo(1.6, 0.7);
        const geomC = new THREE.ExtrudeGeometry(shapeC, extrudeSettings);
        const meshC = new THREE.Mesh(geomC, premiumMaterial);
        meshC.castShadow = true;
        meshC.receiveShadow = true;

        // Илова ба саҳна
        scene.add(meshT);
        scene.add(meshF);
        scene.add(meshC);

        // --- 4. Илова кардани матни "Кулоб Сити" ---
        const fontLoader = new THREE.FontLoader();
        fontLoader.load('https://unpkg.com/three@0.128.0/examples/fonts/helvetiker_regular.typeface.json', function (font) {
            const textGeometry = new THREE.TextGeometry('Кулоб Сити', {
                font: font,
                size: 0.4,
                height: 0.1,
                curveSegments: 12,
                bevelEnabled: true,
                bevelThickness: 0.02,
                bevelSize: 0.02,
                bevelOffset: 0,
                bevelSegments: 5
            });
            textGeometry.computeBoundingBox();
            const textWidth = textGeometry.boundingBox.max.x - textGeometry.boundingBox.min.x;
            const textMaterial = new THREE.MeshPhysicalMaterial({
                color: 0xFFD700, // Тиллоӣ
                roughness: 0.3,
                metalness: 0.7,
                clearcoat: 0.8,
                clearcoatRoughness: 0.1
            });
            const textMesh = new THREE.Mesh(textGeometry, textMaterial);
            textMesh.position.set(-textWidth / 2, -1.8, 0); // Дар поёни логотип ҷойгир кунед
            textMesh.castShadow = true;
            textMesh.receiveShadow = true;
            scene.add(textMesh);
            // Аниматсияи матнро ба timeline илова кунед
            tl.from(textMesh.position, { y: -3, duration: 1.5, ease: "power3.out" }, 1.5);
            tl.from(textMesh.material, { opacity: 0, duration: 1, ease: "power1.out" }, 1.8);
        });
        // --- 4. АНИМАТСИЯИ ХОС ВА СИНАМОӢ (GSAP) ---
        function runAnimation() {
            gsap.killTweensOf([meshT.position, meshT.rotation, meshF.position, meshF.rotation, meshC.position, meshC.rotation, camera.position]);

            // Ҳолати аввалия (Шаклҳо аз беруни экран бо чархзанӣ меоянд)
            meshT.position.set(-12, 6, -4);
            meshT.rotation.set(-2, 1, -1.5);

            meshF.position.set(0, -12, -2);
            meshF.rotation.set(1.5, 1.5, 0.5);

            meshC.position.set(12, -4, -4);
            meshC.rotation.set(0.5, -2, 2);

            // Камера ҳам ҳаракат мекунад (барои эффекти 3D-и воқеӣ)
            camera.position.set(0, 0, 14);

            const tl = gsap.timeline();

            // Гузариши ниҳоят мулоим (power4.out)
            tl.to(meshT.position, { x: 0, y: 0, z: 0, duration: 2.5, ease: "power4.out" }, 0)
              .to(meshT.rotation, { x: 0, y: 0, z: 0, duration: 2.8, ease: "power3.out" }, 0);

            tl.to(meshF.position, { x: 0, y: 0, z: 0, duration: 2.7, ease: "power4.out" }, 0.15)
              .to(meshF.rotation, { x: 0, y: 0, z: 0, duration: 2.9, ease: "power3.out" }, 0.15);

            tl.to(meshC.position, { x: 0, y: 0, z: 0, duration: 2.9, ease: "power4.out" }, 0.3)
              .to(meshC.rotation, { x: 0, y: 0, z: 0, duration: 3.1, ease: "power3.out" }, 0.3);

            // Наздикшавии сусти камера ба логотип ва ҳаракати ночиз
            tl.to(camera.position, { 
                z: 8, 
                x: 0.5, 
                y: 0.2, 
                duration: 3.5, 
                ease: "power2.out" 
            }, 0);
            tl.to(camera.rotation, { 
                x: -0.02, 
                y: 0.05, 
                duration: 3.5, 
                ease: "power2.out" 
            }, 0);
        }

        // Оғози аввалин
        runAnimation();

        document.getElementById('replay-btn').addEventListener('click', runAnimation);
        
        // --- 5. Сатҳи замин бо инъикос ---
        const groundGeometry = new THREE.PlaneGeometry(20, 20);
        const groundMaterial = new THREE.MeshPhysicalMaterial({ color: 0x0A0A0A, roughness: 0.2, metalness: 0.8, reflectivity: 0.5 });
        const ground = new THREE.Mesh(groundGeometry, groundMaterial);
        ground.rotation.x = -Math.PI / 2;
        ground.position.y = -2.5; // Дар поёни логотип
        ground.receiveShadow = true;
        scene.add(ground);

        // --- 5. СИКЛИ РЕНДЕР (Render Loop) ---
        function animate() {
            requestAnimationFrame(animate);
            
            // Сабукфикрона ва нарм давр задани логотип баъди ҷамъ шудан
            const time = Date.now() * 0.0005;
            if(meshT.position.x === 0) {
                // Чархзании сусти ороишӣ
                meshT.parent.rotation.y = Math.sin(time) * 0.08;
                meshT.parent.rotation.x = Math.cos(time) * 0.05;
            }

            composer.render(); // Рендер бо эффекти Bloom
        }
        animate();

        // Адаптатсия ба андозаи экран
        window.addEventListener('resize', () => {
            camera.aspect = window.innerWidth / window.innerHeight;
            camera.updateProjectionMatrix();
            renderer.setSize(window.innerWidth, window.innerHeight); // Update renderer size
            composer.setSize(window.innerWidth, window.innerHeight); // Update composer size
        });
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(debug=True)