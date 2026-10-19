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


def setup_photoreal_materials(use_bevel=True):
    """Varre todos os materiais do modelo e aplica shaders PBR de alta fidelidade para marcenaria."""
    for mat in bpy.data.materials:
        if not mat.node_tree:
            continue
        nodes = mat.node_tree.nodes
        links = mat.node_tree.links
        bsdf = next((n for n in nodes if n.type == "BSDF_PRINCIPLED"), None)
        if bsdf is None:
            continue

        name_lower = (mat.name or "").lower()

        # ── 1. Injeta Nó de Bevel (Chanfro / Quina Arredondada Fotorrealista) ──
        if use_bevel:
            # Só adiciona se o render for Cycles (Bevel shader é recurso nativo do Cycles)
            bevel_node = nodes.new("ShaderNodeBevel")
            bevel_node.inputs["Radius"].default_value = 0.0015  # Raio de 1.5mm (escala de fita de borda de marcenaria)
            bevel_node.samples = 8
            links.new(bevel_node.outputs["Normal"], bsdf.inputs["Normal"])

        # ── 2. Classificação Inteligente de Materiais de Marcenaria ──
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
            # Branco quente acolhedor ~3000K
            _set_bsdf_prop(bsdf, ("Emission Color",), (1.0, 0.85, 0.65, 1.0))

        # Madeiras / MDFs e Lacas
        else:
            # Laca Brilhante
            if "brilho" in name_lower or "gloss" in name_lower:
                _set_bsdf_prop(bsdf, ("Roughness",), 0.1)
                _set_bsdf_prop(bsdf, ("Coat Weight", "Clearcoat"), 0.6)
                _set_bsdf_prop(bsdf, ("Coat Roughness", "Clearcoat Roughness"), 0.03)
            # MDF Madeirado Padrão / Trama Texturizada
            else:
                _set_bsdf_prop(bsdf, ("Roughness",), 0.38)
                _set_bsdf_prop(bsdf, ("Specular IOR Level", "Specular"), 0.45)
                # Adiciona micro-rugosidade tátil aos veios da chapa
                noise = nodes.new("ShaderNodeTexNoise")
                noise.inputs["Scale"].default_value = 25.0
                if "Detail" in noise.inputs:
                    noise.inputs["Detail"].default_value = 4.0
                bump = nodes.new("ShaderNodeBump")
                bump.inputs["Strength"].default_value = 0.035
                if "Distance" in bump.inputs:
                    bump.inputs["Distance"].default_value = 0.005
                links.new(noise.outputs["Fac"], bump.inputs["Height"])
                if use_bevel and 'bevel_node' in locals():
                    links.new(bevel_node.outputs["Normal"], bump.inputs["Normal"])
                links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])


def set_architectural_camera(scene, cam_cfg, width, height, correct_verticals=True):
    """Cria uma câmera de arquitetura com correção de perspectiva vertical."""
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

    # Se a correção de verticais de arquitetura estiver ativa:
    if correct_verticals and abs(fwd.z) > 0.01:
        # Mantém a câmera nivelada com o horizonte (pitch = 0) e usa shift_y para enquadrar
        fwd_level = Vector((fwd.x, fwd.y, 0.0)).normalized()
        true_up_level = Vector((0.0, 0.0, 1.0))
        right_level = fwd_level.cross(true_up_level).normalized()
        rot = Matrix((right_level, true_up_level, -fwd_level)).transposed()
        cam_obj.matrix_world = Matrix.Translation(eye) @ rot.to_4x4()

        # Calcula o deslocamento vertical óptico (Shift Y)
        dist_h = math.hypot(target.x - eye.x, target.y - eye.y)
        if dist_h > 1e-3:
            delta_z = target.z - eye.z
            cam_data.shift_y = (delta_z / dist_h) * 0.5
    else:
        rot = Matrix((right, true_up, -fwd)).transposed()
        cam_obj.matrix_world = Matrix.Translation(eye) @ rot.to_4x4()

    cam_data.sensor_fit = "VERTICAL"
    if cam_cfg.get("perspective", True):
        cam_data.type = "PERSP"
        cam_data.angle_y = math.radians(cam_cfg.get("fov_deg", 50.0))
    else:
        cam_data.type = "ORTHO"
        cam_data.ortho_scale = 2.0 * cam_cfg.get("half_height", 2.0)

    cam_data.clip_start = 0.05
    cam_data.clip_end = 2000.0
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

    # 2. Configura Materiais Fotorrealistas de Marcenaria
    setup_photoreal_materials(use_bevel=use_bevel)

    # 3. Câmera Arquitetônica
    w, h = int(job.get("width", 1920)), int(job.get("height", 1080))
    correct_vert = bool(job.get("correct_verticals", True))
    set_architectural_camera(scene, job["camera"], w, h, correct_verticals=correct_vert)

    # 4. Iluminação e Ambiente
    preset = job.get("preset", "dia")
    sun_dir = job.get("sun")
    apply_lighting_preset(scene, preset_name=preset, sun_dir=sun_dir)

    # 5. Adiciona Luzes Pontuais / Spots enviados pelo usuário
    lights = job.get("lights") or []
    for i, lt in enumerate(lights):
        kind = "SPOT" if lt.get("kind") == "spot" else "POINT"
        ldata = bpy.data.lights.new(f"TrazoLight_{i+1}", type=kind)
        ldata.energy = float(lt.get("power", 400.0))
        ldata.color = tuple(lt.get("color", (1.0, 0.9, 0.8)))
        if hasattr(ldata, "shadow_soft_size"):
            ldata.shadow_soft_size = 0.12  # Lâmpada física com sombra macia
        lobj = bpy.data.objects.new(ldata.name, ldata)
        scene.collection.objects.link(lobj)
        lobj.location = Vector(lt.get("pos", (0, 0, 1)))

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
    view.exposure = float(job.get("exposure", -0.3))
    for look in ("AgX - Medium High Contrast", "Medium High Contrast", "Punchy"):
        try:
            view.look = look
            break
        except Exception:
            pass

    say("rendering", f"{w}x{h}", engine_name, f"samples={samples}")
    bpy.ops.render.render(write_still=True)
    say("done", job["output"])


if __name__ == "__main__":
    main()
