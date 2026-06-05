from flask import Flask, render_template_string

app = Flask(__name__)

# Шаблони махсус барои аниматсияи синамоии TFC
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="tg">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TFC | Cinematic Logo Reveal</title>
    <style>
        body { margin: 0; padding: 0; overflow: hidden; background-color: #050505; }
        #canvas-container { width: 100vw; height: 100vh; display: block; }
        #replay-btn {
            position: absolute; bottom: 40px; left: 50%; transform: translateX(-50%);
            padding: 12px 30px; background: rgba(228, 0, 43, 0.9); color: white;
            border: none; border-radius: 50px; cursor: pointer; font-weight: bold;
            text-transform: uppercase; letter-spacing: 2px; backdrop-filter: blur(10px);
            transition: 0.3s; z-index: 100;
        }
        #replay-btn:hover { background: #ff0000; transform: translateX(-50%) scale(1.05); }
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
    <button id="replay-btn">Намоиши Дубора</button>

    <script>
        let scene, camera, renderer, composer, meshT, meshF, meshC, textMesh, tl;

        function init() {
            scene = new THREE.Scene();
            scene.background = new THREE.Color(0x020202);

            camera = new THREE.PerspectiveCamera(40, window.innerWidth / window.innerHeight, 0.1, 100);
            camera.position.set(0, 0, 12);

            renderer = new THREE.WebGLRenderer({ antialias: true });
            renderer.setSize(window.innerWidth, window.innerHeight);
            renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
            renderer.toneMapping = THREE.ACESFilmicToneMapping;
            renderer.toneMappingExposure = 1.2;
            document.getElementById('canvas-container').appendChild(renderer.domElement);

            // --- Post-processing (Bloom) ---
            const renderPass = new THREE.RenderPass(scene, camera);
            const bloomPass = new THREE.UnrealBloomPass(new THREE.Vector2(window.innerWidth, window.innerHeight), 1.5, 0.4, 0.85);
            bloomPass.threshold = 0.15;
            bloomPass.strength = 1.4;
            bloomPass.radius = 0.6;
            
            composer = new THREE.EffectComposer(renderer);
            composer.addPass(renderPass);
            composer.addPass(bloomPass);

            // --- Lighting ---
            scene.add(new THREE.AmbientLight(0xffffff, 0.3));
            const pointLight = new THREE.PointLight(0xff0000, 2, 20);
            pointLight.position.set(5, 5, 5);
            scene.add(pointLight);
            
            const blueLight = new THREE.DirectionalLight(0x00aaff, 0.8);
            blueLight.position.set(-5, 3, 5);
            scene.add(blueLight);

            // --- Materials ---
            const tfcMaterial = new THREE.MeshPhysicalMaterial({
                color: 0x8B0000, 
                metalness: 0.9, 
                roughness: 0.1, 
                clearcoat: 1.0, 
                sheen: 1.0, 
                sheenColor: 0xffd700
            });

            const extrudeSettings = { depth: 0.4, bevelEnabled: true, bevelThickness: 0.1, bevelSize: 0.1, bevelSegments: 8 };

            // T Shape
            const shapeT = new THREE.Shape();
            shapeT.moveTo(-2.2, 1.5); shapeT.lineTo(-0.8, 1.5); shapeT.lineTo(-0.8, -1.5); 
            shapeT.lineTo(-1.3, -1.5); shapeT.lineTo(-1.3, 1.0); shapeT.lineTo(-2.2, 1.0);
            meshT = new THREE.Mesh(new THREE.ExtrudeGeometry(shapeT, extrudeSettings), tfcMaterial);

            // F Shape
            const shapeF = new THREE.Shape();
            shapeF.moveTo(-0.4, 1.5); shapeF.lineTo(1.0, 1.5); shapeF.lineTo(1.0, 1.1); shapeF.lineTo(0.1, 1.1);
            shapeF.lineTo(0.1, 0.3); shapeF.lineTo(0.8, 0.3); shapeF.lineTo(0.8, -0.1); shapeF.lineTo(0.1, -0.1);
            shapeF.lineTo(0.1, -1.5); shapeF.lineTo(-0.4, -1.5);
            meshF = new THREE.Mesh(new THREE.ExtrudeGeometry(shapeF, extrudeSettings), tfcMaterial);

            // C Shape
            const shapeC = new THREE.Shape();
            shapeC.absarc(2.2, 0, 1.5, Math.PI * 0.2, Math.PI * 1.8, false);
            shapeC.lineTo(2.0, -1.2);
            shapeC.absarc(2.2, 0, 1.1, Math.PI * 1.8, Math.PI * 0.2, true);
            meshC = new THREE.Mesh(new THREE.ExtrudeGeometry(shapeC, extrudeSettings), tfcMaterial);

            scene.add(meshT, meshF, meshC);

            // --- Text ---
            const loader = new THREE.FontLoader();
            loader.load('https://unpkg.com/three@0.128.0/examples/fonts/helvetiker_bold.typeface.json', (font) => {
                const textGeo = new THREE.TextGeometry('KULOB CITY', {
                    font: font, size: 0.5, height: 0.1, bevelEnabled: true, bevelThickness: 0.05, bevelSize: 0.02
                });
                textGeo.computeBoundingBox();
                const centerOffset = -0.5 * (textGeo.boundingBox.max.x - textGeo.boundingBox.min.x);
                textMesh = new THREE.Mesh(textGeo, new THREE.MeshPhysicalMaterial({ color: 0xFFD700, metalness: 0.8, roughness: 0.2 }));
                textMesh.position.set(centerOffset, -2.2, 0);
                scene.add(textMesh);
                runAnimation();
            });

            // --- Ground reflection ---
            const ground = new THREE.Mesh(
                new THREE.PlaneGeometry(20, 20),
                new THREE.MeshPhysicalMaterial({ color: 0x050505, metalness: 0.8, roughness: 0.2, transparent: true, opacity: 0.4 })
            );
            ground.rotation.x = -Math.PI / 2;
            ground.position.y = -3;
            scene.add(ground);

            window.addEventListener('resize', onWindowResize);
            document.getElementById('replay-btn').addEventListener('click', runAnimation);
            animate();
        }

        function runAnimation() {
            if (tl) tl.kill();
            tl = gsap.timeline();

            // Initial State
            gsap.set([meshT.position, meshF.position, meshC.position], { z: -10, y: 5 });
            gsap.set([meshT.rotation, meshF.rotation, meshC.rotation], { x: 2, y: 2 });
            if (textMesh) gsap.set(textMesh.material, { opacity: 0 });

            // Reveal
            tl.to(meshT.position, { y: 0, z: 0, duration: 1.5, ease: "expo.out" }, 0)
              .to(meshT.rotation, { x: 0, y: 0, duration: 2, ease: "power4.out" }, 0);

            tl.to(meshF.position, { y: 0, z: 0, duration: 1.5, ease: "expo.out" }, 0.2)
              .to(meshF.rotation, { x: 0, y: 0, duration: 2, ease: "power4.out" }, 0.2);

            tl.to(meshC.position, { y: 0, z: 0, duration: 1.5, ease: "expo.out" }, 0.4)
              .to(meshC.rotation, { x: 0, y: 0, duration: 2, ease: "power4.out" }, 0.4);

            tl.to(camera.position, { z: 9, duration: 3, ease: "sine.inOut" }, 0);

            if (textMesh) {
                tl.to(textMesh.material, { opacity: 1, duration: 1 }, 1.5);
                tl.from(textMesh.position, { y: -3, duration: 1.2, ease: "back.out(1.7)" }, 1.5);
            }
        }

        function onWindowResize() {
            camera.aspect = window.innerWidth / window.innerHeight;
            camera.updateProjectionMatrix();
            renderer.setSize(window.innerWidth, window.innerHeight);
            composer.setSize(window.innerWidth, window.innerHeight);
        }

        function animate() {
            requestAnimationFrame(animate);
            const time = Date.now() * 0.001;
            
            // Gentle floating motion
            if (meshT) {
                meshT.position.y = Math.sin(time * 0.5) * 0.1;
                meshF.position.y = Math.sin(time * 0.5 + 0.5) * 0.1;
                meshC.position.y = Math.sin(time * 0.5 + 1.0) * 0.1;
            }

            composer.render();
        }

        init();
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    # Порти 5005 барои саҳифаи аниматсияи нави safchk
    app.run(debug=True, port=5005)