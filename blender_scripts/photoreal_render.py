# SPDX-License-Identifier: GPL-3.0-or-later
"""Script autônomo executado internamente pelo Blender em segundo plano (Headless).

Pertence exclusivamente ao TrazoMob. Transforma o modelo exportado em uma cena
de arquitetura e marcenaria foto-realista no Blender (Cycles / EEVEE Next):
1. Bevel Shader em Cycles para arredondamento sutil de quinas de MDF / fitas de borda.
2. Reconhecimento avançado de materiais PBR (MDF Madeirado, Laca, Espelho, Vidro Reflecta, Perfis de Alumínio).
3. Emissão para fitas de LED de marcenaria (luz quente 2700K - 3000K).
4. Câmera arquitetônica com correção de verticais de 2 pontos de fuga (Shift Y).
5. Iluminação de Interiores calibrada (Dia, Tarde/Golden Hour, Noturno com LEDs, Estúdio Showroom).
6. Denoiser via IA (OptiX / OpenImageDenoise) e Color Management AgX com alto contraste.
"""
import json
import math
import sys
import bpy
from mathutils import Matrix, Vector


def say(*parts):
    print("TRAZOMOB_RENDER", *parts, flush=True)


def load_job():
    argv = sys.argv
    if "--" not in argv:
        raise SystemExit("photoreal_render.py: nenhum arquivo job.json passado após '--'")
    job_path = argv[argv.index("--") + 1]
    with open(job_path, encoding="utf-8") as fh:
        return json.load(fh)


def import_model(path):
    bpy.ops.import_scene.gltf(filepath=path)
    objs = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    
    # Aplica normais ponderadas (Weighted Normals) e suavização inteligente de CAD
    for obj in objs:
        # Habilita auto-smooth se disponível na versão do Blender
        if hasattr(obj.data, "use_auto_smooth"):
            obj.data.use_auto_smooth = True
            obj.data.auto_smooth_angle = math.radians(45.0)

        # Adiciona modificador Weighted Normal para quinas de marcenaria nítidas e perfeitas
        mod = obj.modifiers.new(name="TrazoNormals", type="WEIGHTED_NORMAL")
        mod.keep_sharp = True
        mod.weight = 50

    say("imported", len(objs), "objects")
    return objs


def _set_bsdf_prop(bsdf, names, value):
    """Define valor no primeiro socket existente compatível (Blender 3.6 - 5.x)."""
    for n in names:
        sock = bsdf.inputs.get(n)
        if sock is not None:
            try:
                sock.default_value = value
            except (TypeError, ValueError):
                continue
            for link in list(sock.links):
                sock.id_data.links.remove(link)
            return True
    return False


def setup_photoreal_materials(use_bevel=True, material_overrides=None):
    """Varre todos os materiais do modelo e aplica shaders PBR de alta fidelidade para marcenaria,
    respeitando overrides configurados pelo usuário na interface do TrazoMob (tecido, pedra, madeira, etc.).
    """
    overrides = material_overrides or {}

    for mat in bpy.data.materials:
        if not mat.node_tree:
            continue
        nodes = mat.node_tree.nodes
        links = mat.node_tree.links
        bsdf = next((n for n in nodes if n.type == "BSDF_PRINCIPLED"), None)
        if bsdf is None:
            continue

        mat_name = mat.name or ""
        name_lower = mat_name.lower()
        cfg = overrides.get(mat_name) or overrides.get(name_lower) or {}

        # ── 1. Injeta Nó de Bevel (Chanfro / Quina Arredondada Fotorrealista) ──
        bevel_node = None
        if use_bevel:
            bevel_node = nodes.new("ShaderNodeBevel")
            bevel_node.inputs["Radius"].default_value = 0.0015  # Raio de 1.5mm (escala de fita de borda de marcenaria)
            bevel_node.samples = 8
            links.new(bevel_node.outputs["Normal"], bsdf.inputs["Normal"])

        # ── 2. SE O USUÁRIO DEFINIU PRESET EXPLICITAMENTE NO PAINEL ──
        preset_type = cfg.get("type")
        if preset_type:
            roughness = float(cfg.get("roughness", 0.5))
            metallic = float(cfg.get("metallic", 0.0))
            bump_strength = float(cfg.get("bump", 0.02))

            if preset_type == "tecido":
                # Tecido / Estofado / Cortina (Veludo, Linho, Algodão)
                _set_bsdf_prop(bsdf, ("Roughness",), max(0.65, roughness))
                _set_bsdf_prop(bsdf, ("Metallic",), 0.0)
                _set_bsdf_prop(bsdf, ("Specular IOR Level", "Specular"), 0.1)
                _set_bsdf_prop(bsdf, ("Sheen Weight", "Sheen"), 0.85)  # Brilho de penugem nas bordas
                _set_bsdf_prop(bsdf, ("Sheen Roughness",), 0.5)
                # Trama fina de tecido (micro-weave noise)
                noise = nodes.new("ShaderNodeTexNoise")
                noise.inputs["Scale"].default_value = 160.0
                if "Detail" in noise.inputs:
                    noise.inputs["Detail"].default_value = 8.0
                bump = nodes.new("ShaderNodeBump")
                bump.inputs["Strength"].default_value = bump_strength or 0.035
                links.new(noise.outputs["Fac"], bump.inputs["Height"])
                links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
                continue

            elif preset_type == "pedra":
                # Pedra / Mármore / Granito / Quartzo
                is_polido = cfg.get("sub_type", "polido") == "polido"
                _set_bsdf_prop(bsdf, ("Roughness",), roughness if not is_polido else 0.06)
                _set_bsdf_prop(bsdf, ("Metallic",), 0.0)
                _set_bsdf_prop(bsdf, ("Specular IOR Level", "Specular"), 0.85)
                if is_polido:
                    _set_bsdf_prop(bsdf, ("Coat Weight", "Clearcoat"), 0.6)
                    _set_bsdf_prop(bsdf, ("Coat Roughness", "Clearcoat Roughness"), 0.02)
                noise = nodes.new("ShaderNodeTexNoise")
                noise.inputs["Scale"].default_value = 45.0
                if "Detail" in noise.inputs:
                    noise.inputs["Detail"].default_value = 6.0
                bump = nodes.new("ShaderNodeBump")
                bump.inputs["Strength"].default_value = bump_strength or 0.015
                links.new(noise.outputs["Fac"], bump.inputs["Height"])
                if bevel_node:
                    links.new(bevel_node.outputs["Normal"], bump.inputs["Normal"])
                links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
                continue

            elif preset_type == "madeira":
                # Madeira / MDF
                is_gloss = cfg.get("sub_type") == "gloss"
                _set_bsdf_prop(bsdf, ("Roughness",), roughness if not is_gloss else 0.05)
                _set_bsdf_prop(bsdf, ("Metallic",), 0.0)
                _set_bsdf_prop(bsdf, ("Specular IOR Level", "Specular"), 0.5)
                if is_gloss:
                    _set_bsdf_prop(bsdf, ("Coat Weight", "Clearcoat"), 0.85)
                    _set_bsdf_prop(bsdf, ("Coat Roughness", "Clearcoat Roughness"), 0.02)
                else:
                    tex_img_node = next((n for n in nodes if n.type == "TEX_IMAGE"), None)
                    bump = nodes.new("ShaderNodeBump")
                    bump.inputs["Strength"].default_value = bump_strength or 0.035
                    if tex_img_node:
                        links.new(tex_img_node.outputs["Color"], bump.inputs["Height"])
                    else:
                        noise = nodes.new("ShaderNodeTexNoise")
                        noise.inputs["Scale"].default_value = 35.0
                        links.new(noise.outputs["Fac"], bump.inputs["Height"])
                    if bevel_node:
                        links.new(bevel_node.outputs["Normal"], bump.inputs["Normal"])
                    links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
                continue

            elif preset_type == "metal":
                # Metais (Inox, Alumínio, Dourado, Preto)
                _set_bsdf_prop(bsdf, ("Metallic",), 1.0)
                _set_bsdf_prop(bsdf, ("Roughness",), roughness)
                _set_bsdf_prop(bsdf, ("Anisotropic",), 0.35)
                continue

            elif preset_type == "vidro":
                # Vidro / Reflecta
                _set_bsdf_prop(bsdf, ("Transmission Weight", "Transmission"), 1.0)
                _set_bsdf_prop(bsdf, ("Roughness",), roughness)
                _set_bsdf_prop(bsdf, ("IOR",), 1.52)
                continue

            elif preset_type == "couro":
                # Couro / Couro Sintético
                _set_bsdf_prop(bsdf, ("Roughness",), max(0.4, roughness))
                _set_bsdf_prop(bsdf, ("Specular IOR Level", "Specular"), 0.3)
                voronoi = nodes.new("ShaderNodeTexVoronoi")
                voronoi.inputs["Scale"].default_value = 120.0
                bump = nodes.new("ShaderNodeBump")
                bump.inputs["Strength"].default_value = bump_strength or 0.04
                links.new(voronoi.outputs["Distance"], bump.inputs["Height"])
                links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
                continue

        # ── 3. CLASSIFICAÇÃO AUTOMÁTICA INTELIGENTE (SE NÃO TIVER OVERRIDE MANUAL) ──
        # Vidro / Vidro Reflecta
        if any(k in name_lower for k in ("vidro", "glass", "cristal", "reflecta")):
            is_reflecta = "reflecta" in name_lower or "bronze" in name_lower or "fume" in name_lower
            _set_bsdf_prop(bsdf, ("Transmission Weight", "Transmission"), 0.92 if is_reflecta else 1.0)
            _set_bsdf_prop(bsdf, ("Roughness",), 0.02)
            _set_bsdf_prop(bsdf, ("IOR",), 1.52)
            _set_bsdf_prop(bsdf, ("Alpha",), 1.0)
            if is_reflecta:
                _set_bsdf_prop(bsdf, ("Metallic",), 0.25)
            for attr, val in (("blend_method", "OPAQUE"), ("use_screen_refraction", True)):
                if hasattr(mat, attr):
                    try:
                        setattr(mat, attr, val)
                    except Exception:
                        pass

        # Espelho
        elif any(k in name_lower for k in ("espelho", "mirror")):
            _set_bsdf_prop(bsdf, ("Metallic",), 1.0)
            _set_bsdf_prop(bsdf, ("Roughness",), 0.0)
            _set_bsdf_prop(bsdf, ("Base Color",), (0.95, 0.95, 0.95, 1.0))

        # Perfis Metálicos / Puxadores / Inox / Alumínio
        elif any(k in name_lower for k in ("perfil", "aluminio", "inox", "metal", "cobre", "gold", "preto fosco", "puxador")):
            is_gold = "gold" in name_lower or "dourado" in name_lower or "cobre" in name_lower
            is_black = "preto" in name_lower or "black" in name_lower
            _set_bsdf_prop(bsdf, ("Metallic",), 0.85 if not is_black else 0.4)
            _set_bsdf_prop(bsdf, ("Roughness",), 0.22 if not is_black else 0.35)
            _set_bsdf_prop(bsdf, ("Anisotropic",), 0.3)
            if is_gold:
                _set_bsdf_prop(bsdf, ("Base Color",), (0.95, 0.75, 0.4, 1.0))

        # Fitas de LED / Iluminação de Nichos e Painéis
        elif any(k in name_lower for k in ("led", "emissao", "luz", "iluminacao")):
            _set_bsdf_prop(bsdf, ("Emission Strength", "Emission"), 8.0)
            _set_bsdf_prop(bsdf, ("Emission Color",), (1.0, 0.85, 0.65, 1.0))

        # Tecidos / Cortinas / Sofá
        elif any(k in name_lower for k in ("tecido", "fabric", "linho", "veludo", "cortina", "sofa", "almofada", "couro")):
            _set_bsdf_prop(bsdf, ("Roughness",), 0.75)
            _set_bsdf_prop(bsdf, ("Sheen Weight", "Sheen"), 0.8)
            noise = nodes.new("ShaderNodeTexNoise")
            noise.inputs["Scale"].default_value = 140.0
            bump = nodes.new("ShaderNodeBump")
            bump.inputs["Strength"].default_value = 0.03
            links.new(noise.outputs["Fac"], bump.inputs["Height"])
            links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])

        # Tintas de Parede e Alvenaria / Drywall / Gesso
        elif any(k in name_lower for k in ("parede", "wall", "tinta", "paint", "alvenaria", "gesso", "cimento")):
            is_cimento = "cimento" in name_lower or "concreto" in name_lower
            _set_bsdf_prop(bsdf, ("Roughness",), 0.88 if not is_cimento else 0.75)
            _set_bsdf_prop(bsdf, ("Specular IOR Level", "Specular"), 0.18)
            noise = nodes.new("ShaderNodeTexNoise")
            noise.inputs["Scale"].default_value = 80.0 if not is_cimento else 25.0
            if "Detail" in noise.inputs:
                noise.inputs["Detail"].default_value = 5.0
            bump = nodes.new("ShaderNodeBump")
            bump.inputs["Strength"].default_value = 0.012 if not is_cimento else 0.035
            links.new(noise.outputs["Fac"], bump.inputs["Height"])
            links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])

        # Mármores, Pedras e Granitos
        elif any(k in name_lower for k in ("granito", "marmore", "mármore", "quartzo", "silestone", "calacatta", "pietra", "armani", "pedra")):
            _set_bsdf_prop(bsdf, ("Roughness",), 0.08)
            _set_bsdf_prop(bsdf, ("Specular IOR Level", "Specular"), 0.85)
            _set_bsdf_prop(bsdf, ("Coat Weight", "Clearcoat"), 0.5)
            _set_bsdf_prop(bsdf, ("Coat Roughness", "Clearcoat Roughness"), 0.02)
            noise = nodes.new("ShaderNodeTexNoise")
            noise.inputs["Scale"].default_value = 40.0
            if "Detail" in noise.inputs:
                noise.inputs["Detail"].default_value = 8.0
            bump = nodes.new("ShaderNodeBump")
            bump.inputs["Strength"].default_value = 0.015
            links.new(noise.outputs["Fac"], bump.inputs["Height"])
            if bevel_node:
                links.new(bevel_node.outputs["Normal"], bump.inputs["Normal"])
            links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])

        # Madeiras / MDFs e Lacas
        else:
            if "brilho" in name_lower or "gloss" in name_lower or "laca" in name_lower:
                _set_bsdf_prop(bsdf, ("Roughness",), 0.06)
                _set_bsdf_prop(bsdf, ("Coat Weight", "Clearcoat"), 0.8)
                _set_bsdf_prop(bsdf, ("Coat Roughness", "Clearcoat Roughness"), 0.02)
            else:
                _set_bsdf_prop(bsdf, ("Roughness",), 0.32)
                _set_bsdf_prop(bsdf, ("Specular IOR Level", "Specular"), 0.5)

                tex_img_node = next((n for n in nodes if n.type == "TEX_IMAGE"), None)
                bump = nodes.new("ShaderNodeBump")
                bump.inputs["Strength"].default_value = 0.04
                if "Distance" in bump.inputs:
                    bump.inputs["Distance"].default_value = 0.003

                if tex_img_node:
                    links.new(tex_img_node.outputs["Color"], bump.inputs["Height"])
                else:
                    noise = nodes.new("ShaderNodeTexNoise")
                    noise.inputs["Scale"].default_value = 35.0
                    if "Detail" in noise.inputs:
                        noise.inputs["Detail"].default_value = 6.0
                    if "Roughness" in noise.inputs:
                        noise.inputs["Roughness"].default_value = 0.7
                    links.new(noise.outputs["Fac"], bump.inputs["Height"])

                if bevel_node:
                    links.new(bevel_node.outputs["Normal"], bump.inputs["Normal"])
                links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])



def set_architectural_camera(scene, cam_cfg, width, height, correct_verticals=False):
    """Cria uma câmera perfeitamente alinhada com o viewport do IngeTrazo.
    
    Reproduz com precisão milimétrica a matriz do IngeTrazo (resources/blender/render_scene.py)
    e suporta o modo Two-Point Perspective caso o usuário queira verticais corrigidas.
    """
    cam_data = bpy.data.cameras.new("TrazoMob_Cam")
    cam_obj = bpy.data.objects.new("TrazoMob Camera", cam_data)
    scene.collection.objects.link(cam_obj)
    scene.camera = cam_obj

    eye = Vector(cam_cfg["eye"])
    target = Vector(cam_cfg["target"])
    up = Vector(cam_cfg["up"])

    fwd = (target - eye).normalized()
    right = fwd.cross(up)
    if right.length < 1e-9:
        right = fwd.cross(Vector((0.0, 1.0, 0.0)))
    right.normalize()
    true_up = right.cross(fwd).normalized()

    # Se 'correct_verticals' estiver marcado (ou a câmera original já for two_point):
    if correct_verticals and abs(fwd.z) > 0.01:
        fwd_level = Vector((fwd.x, fwd.y, 0.0)).normalized()
        true_up_level = Vector((0.0, 0.0, 1.0))
        right_level = fwd_level.cross(true_up_level).normalized()
        rot = Matrix((right_level, true_up_level, -fwd_level)).transposed()
        cam_obj.matrix_world = Matrix.Translation(eye) @ rot.to_4x4()

        # O deslocamento óptico correto do frustum no Blender (Shift Y):
        # target_rel = target - eye.
        # depth = target_rel . level_forward
        # shift_y = rel.z / depth
        rel = target - eye
        depth = rel.dot(fwd_level)
        if abs(depth) > 1e-4:
            fov_rad = math.radians(cam_cfg.get("fov_deg", 45.0))
            # No Blender, shift_y = 1.0 desloca exatamente meia altura do sensor.
            # O ângulo de visão vertical corresponde a 2 * atan(half_sensor / focal)
            # Portanto shift_y = (rel.z / depth) / tan(fov / 2)
            half_tan = math.tan(fov_rad / 2.0)
            if half_tan > 1e-4:
                cam_data.shift_y = (rel.z / depth) / (2.0 * half_tan)
    else:
        # Modo 100% idêntico ao viewport do IngeTrazo
        rot = Matrix((right, true_up, -fwd)).transposed()
        cam_obj.matrix_world = Matrix.Translation(eye) @ rot.to_4x4()

    cam_data.sensor_fit = "VERTICAL"
    if cam_cfg.get("perspective", True):
        cam_data.type = "PERSP"
        cam_data.angle_y = math.radians(cam_cfg.get("fov_deg", 45.0))
    else:
        cam_data.type = "ORTHO"
        cam_data.ortho_scale = 2.0 * cam_cfg.get("half_height", 2.0) * max(
            1.0, width / max(height, 1)
        )

    cam_data.clip_start = max(cam_cfg.get("near", 0.05), 1e-4)
    cam_data.clip_end = max(cam_cfg.get("far", 1e5), cam_data.clip_start * 10)
    return cam_obj


def apply_lighting_preset(scene, preset_name="dia", sun_dir=None):
    """Aplica iluminação profissional de ambientes internos."""
    world = bpy.data.worlds.new(f"TrazoMob_World_{preset_name}")
    scene.world = world
    if hasattr(world, "use_nodes"):
        world.use_nodes = True
    nodes = world.node_tree.nodes
    links = world.node_tree.links
    bg = nodes.get("Background") or nodes.new("ShaderNodeBackground")

    if preset_name in ("dia", "tarde"):
        sky = nodes.new("ShaderNodeTexSky")
        try:
            sky.sky_type = "NISHITA"
        except Exception:
            pass
        if sun_dir:
            d = Vector(sun_dir).normalized()
            if preset_name == "tarde":
                # Força sol mais baixo e quente no horizonte
                d = Vector((d.x, d.y, max(0.12, d.z * 0.35))).normalized()
            elevation = math.asin(max(-1.0, min(1.0, d.z)))
            rotation = math.atan2(d.x, d.y)
            if hasattr(sky, "sun_elevation"):
                sky.sun_elevation = elevation
            if hasattr(sky, "sun_rotation"):
                sky.sun_rotation = -rotation + math.pi / 2
            if hasattr(sky, "sun_disc"):
                sky.sun_disc = True

            # Cria Sol Físico Directional
            sun_light = bpy.data.lights.new("TrazoMob Sun", type="SUN")
            sun_light.energy = 4.5 if preset_name == "dia" else 3.2
            sun_light.angle = math.radians(1.2)  # Sol suave (sombras mais macias)
            if preset_name == "tarde":
                sun_light.color = (1.0, 0.78, 0.52)  # Dourado entardecer
            sun_obj = bpy.data.objects.new("TrazoMob Sun", sun_light)
            scene.collection.objects.link(sun_obj)
            sun_obj.rotation_euler = d.to_track_quat("Z", "Y").to_euler()

        links.new(sky.outputs["Color"], bg.inputs["Color"])
        bg.inputs["Strength"].default_value = 0.4 if preset_name == "dia" else 0.25

    elif preset_name == "noturno":
        # Céu noturno escuro com azul profundo
        bg.inputs["Color"].default_value = (0.012, 0.018, 0.038, 1.0)
        bg.inputs["Strength"].default_value = 0.5

    elif preset_name == "estudio":
        # Ambiente de Estúdio Comercial (luz suave difusa, sem sol direto duro)
        bg.inputs["Color"].default_value = (0.92, 0.94, 0.96, 1.0)
        bg.inputs["Strength"].default_value = 1.0


def setup_render_engine(scene, engine="cycles", samples=128):
    """Configura Cycles ou EEVEE com Denoiser de IA e detecção de GPU."""
    if engine == "cycles":
        scene.render.engine = "CYCLES"
        scene.cycles.samples = samples
        scene.cycles.use_denoising = True
        try:
            # Tenta ativar OpenImageDenoise ou OptiX
            scene.cycles.denoiser = "OPENIMAGEDENOISE"
        except Exception:
            pass

        # Ativa aceleração por GPU se disponível
        try:
            prefs = bpy.context.preferences.addons["cycles"].preferences
            for backend in ("OPTIX", "CUDA", "HIP", "METAL", "ONEAPI"):
                try:
                    prefs.compute_device_type = backend
                except TypeError:
                    continue
                prefs.get_devices()
                gpus = [d for d in prefs.devices if d.type == backend]
                if gpus:
                    for d in prefs.devices:
                        d.use = d.type in (backend, "CPU")
                    scene.cycles.device = "GPU"
                    say("gpu_enabled", backend)
                    break
        except Exception:
            pass
    else:
        # EEVEE Next ou EEVEE Padrão
        for name in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
            try:
                scene.render.engine = name
                break
            except Exception:
                continue
        if hasattr(scene.eevee, "taa_render_samples"):
            scene.eevee.taa_render_samples = min(samples, 64)
        for flag in ("use_shadows", "use_raytracing", "use_gtao", "use_ssr", "use_ssr_refraction"):
            if hasattr(scene.eevee, flag):
                try:
                    setattr(scene.eevee, flag, True)
                except Exception:
                    pass


def main():
    job = load_job()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene

    # 1. Importa Modelo GLB
    import_model(job["glb"])

    engine_name = job.get("engine", "cycles")
    use_bevel = (engine_name == "cycles")

    # 2. Configura Materiais Fotorrealistas de Marcenaria e Overrides
    material_overrides = job.get("materials") or {}
    setup_photoreal_materials(use_bevel=use_bevel, material_overrides=material_overrides)

    # 3. Câmera Arquitetônica
    w, h = int(job.get("width", 1920)), int(job.get("height", 1080))
    correct_vert = bool(job.get("correct_verticals", True))
    set_architectural_camera(scene, job["camera"], w, h, correct_verticals=correct_vert)

    # 4. Iluminação e Ambiente
    preset = job.get("preset", "dia")
    sun_dir = job.get("sun")
    apply_lighting_preset(scene, preset_name=preset, sun_dir=sun_dir)

    # 4.1 Luz de Preenchimento Suave (Só ativada quando o usuário NÃO configurou lâmpadas próprias)
    # Se o usuário inseriu luzes na cena, respeita 100% a iluminação real do usuário (estilo Kerkythea)
    lights = job.get("lights") or []
    has_user_lights = len(lights) > 0

    if not has_user_lights and preset != "manual":
        cam_cfg = job["camera"]
        eye_pos = Vector(cam_cfg["eye"])
        target_pos = Vector(cam_cfg["target"])
        fill_pos = eye_pos + (target_pos - eye_pos) * 0.35 + Vector((0, 0, 1.2))

        fill_light = bpy.data.lights.new("TrazoMob_Fill_Softbox", type="AREA")
        fill_light.energy = 220.0 if preset == "dia" else (160.0 if preset == "tarde" else 90.0)
        fill_light.size = 2.5
        fill_light.size_y = 2.5
        fill_light.color = (1.0, 0.95, 0.90) if preset != "noturno" else (1.0, 0.85, 0.70)
        fill_obj = bpy.data.objects.new("TrazoMob_Fill_Softbox", fill_light)
        scene.collection.objects.link(fill_obj)
        fill_obj.location = fill_pos
        fill_dir = (target_pos - fill_pos).normalized()
        fill_obj.rotation_euler = fill_dir.to_track_quat("-Z", "Y").to_euler()

    # 5. Adiciona Luzes Pontuais / Spots / Fitas LED enviadas pelo usuário (Kerkythea / V-Ray style)
    for i, lt in enumerate(lights):
        raw_kind = lt.get("kind", "point")
        color = tuple(lt.get("color", (1.0, 0.9, 0.8)))
        power = float(lt.get("power", 400.0))

        if raw_kind == "led_strip" and "p1" in lt and "p2" in lt:
            p1 = Vector(lt["p1"])
            p2 = Vector(lt["p2"])
            diff = p2 - p1
            length = diff.length
            if length < 1e-4:
                length = 0.5
                mid = p1
                dir_strip = Vector((1.0, 0.0, 0.0))
            else:
                mid = (p1 + p2) * 0.5
                dir_strip = diff.normalized()

            # Cria luz física tipo AREA retangular no formato da fita LED / perfil de alumínio
            ldata = bpy.data.lights.new(f"TrazoLED_{i+1}", type="AREA")
            ldata.shape = "RECTANGLE"
            ldata.size = length
            ldata.size_y = 0.02  # 20mm de largura do perfil
            ldata.energy = power
            ldata.color = color

            lobj = bpy.data.objects.new(ldata.name, ldata)
            scene.collection.objects.link(lobj)
            # Desloca 2mm da superfície na direção do facho para baixo (-Z padrão ou dir)
            fwd_light = Vector(lt.get("dir", (0.0, 0.0, -1.0))).normalized()
            lobj.location = mid + fwd_light * 0.005

            # Orienta: -Z da luz alinhado com fwd_light, e eixo X da luz alinhado com a fita dir_strip
            z_axis = -fwd_light
            x_axis = dir_strip
            y_axis = z_axis.cross(x_axis).normalized()
            x_axis = y_axis.cross(z_axis).normalized()
            mat_rot = Matrix((x_axis, y_axis, z_axis)).transposed().to_4x4()
            lobj.matrix_world = Matrix.Translation(lobj.location) @ mat_rot
            continue

        kind = "SPOT" if raw_kind == "spot" else "POINT"
        ldata = bpy.data.lights.new(f"TrazoLight_{i+1}", type=kind)
        ldata.energy = power
        ldata.color = color
        if hasattr(ldata, "shadow_soft_size"):
            ldata.shadow_soft_size = 0.08  # Lâmpada física com sombra realista
        if kind == "SPOT":
            spot_ang = math.radians(float(lt.get("angle", 60.0)))
            ldata.spot_size = spot_ang
            ldata.spot_blend = 0.25

        lobj = bpy.data.objects.new(ldata.name, ldata)
        scene.collection.objects.link(lobj)
        lobj.location = Vector(lt.get("pos", (0, 0, 1)))

        # Se for Spot, orienta o cone de luz na direção do alvo/mira (target ou dir)
        if kind == "SPOT":
            if "target" in lt:
                t_pos = Vector(lt["target"])
                d = (t_pos - lobj.location).normalized()
            elif "dir" in lt:
                d = Vector(lt["dir"]).normalized()
            else:
                d = Vector((0.0, 0.0, -1.0))
            if d.length > 1e-4:
                lobj.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()


    # 6. Motor de Render e Qualidade
    samples = int(job.get("samples", 128))
    setup_render_engine(scene, engine=engine_name, samples=samples)

    # 7. Color Management Profissional (AgX / Filmic High Contrast)
    scene.render.resolution_x = w
    scene.render.resolution_y = h
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = job["output"]

    view = scene.view_settings
    view.exposure = float(job.get("exposure", 0.0))
    for look in ("AgX - Medium High Contrast", "AgX - High Contrast", "Medium High Contrast", "Punchy"):
        try:
            view.look = look
            break
        except Exception:
            pass

    # Salva o arquivo .blend completo para inspeção direta se solicitado
    blend_path = job.get("blend_file")
    if blend_path:
        try:
            bpy.ops.wm.save_as_mainfile(filepath=blend_path)
            say("saved_blend", blend_path)
        except Exception:
            pass

    say("rendering", f"{w}x{h}", engine_name, f"samples={samples}")
    bpy.ops.render.render(write_still=True)
    say("done", job["output"])


if __name__ == "__main__":
    main()
