"""0347: run the Godot scene per (effect, route), turn the PNG sequence into a 2x nearest-neighbour GIF in gifs/."""
import subprocess, sys, shutil
from pathlib import Path
from PIL import Image
H = Path(__file__).resolve().parent
GODOT = "C:/Homespace/[software]/Godot/Godot_v4.7.2-stable_win64_console.exe"
JOBS = [("hit_spark","b"),("hit_spark","d"),("sound_wave","c"),("sound_wave","d"),("summon_puff","c"),("summon_puff","d"),
        ("buff_glow","c"),("buff_glow","d"),("telegraph","b"),("telegraph","d")]
(H/"gifs").mkdir(exist_ok=True)
for eff, route in JOBS:
    work = H/"gif_work"/f"{eff}_{route}"; shutil.rmtree(work, ignore_errors=True); work.mkdir(parents=True)
    subprocess.run([GODOT, "--path", str(H/"godot_project"), "--write-movie", f"{work.as_posix()}/f.png", "--fixed-fps", "12",
                    "--quit-after", "36", "--", eff, route, (H/"frames").as_posix()], capture_output=True, timeout=300)
    pngs = sorted(work.glob("f*.png"))
    ims = [Image.open(p).convert("RGB") for p in pngs]
    ims2 = [i.resize((i.width*2, i.height*2), Image.NEAREST) for i in ims]
    ims2[0].save(H/"gifs"/f"{eff}.{route}.gif", save_all=True, append_images=ims2[1:], duration=83, loop=0)
    # a still contact: 4 frames chosen
    ims[len(ims)//12*1].save(H/"gifs"/f"{eff}.{route}.still.png")
    print(eff, route, len(ims))
shutil.rmtree(H/"gif_work")
