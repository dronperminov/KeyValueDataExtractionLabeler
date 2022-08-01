import json
import os
import shutil
import urllib.parse
import random
from typing import List
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.status import HTTP_302_FOUND


app = FastAPI()
with open("config.json", encoding="utf-8") as f:
    config = json.load(f)

images_path = config.get("images_path", "images")
output_path = config.get("output_path", "labeled")
output_name = config.get("output_name", "labeled.json")
labeled_path = os.path.join(output_path, output_name)

os.makedirs(output_path, exist_ok=True)

app.mount("/images", StaticFiles(directory=images_path), name="images")
app.mount("/styles", StaticFiles(directory="styles"), name="styles")


def get_labeled_data() -> dict:
    if not os.path.exists(labeled_path):
        return {}

    with open(labeled_path, encoding="utf-8") as f:
        labeled_data = json.load(f)

    return labeled_data


def key_to_html(key: dict, data: dict) -> str:
    key_type = key.get("type", "str")
    key_name = key["name"]
    key_title = key.get("title", key_name)
    value = data.get(key_name, "")

    if key_type == "str":
        key_html = f'<label>{key_title}<input type="text" name={key_name} value=\'{value}\'></label>'
    elif key_type == "multiline_str":
        key_html = f'<label>{key_title}<textarea name={key_name}>{value}</textarea></label>'
    elif key_type == "checkbox":
        key_html = f'<label><input type="checkbox" name={key_name}{" checked" if value else ""}>{key_title}</label>'
    elif key_type == "select":
        options = "\n".join([f'<option value="{option}"{" selected" if option == value else ""}>{option}</option>' for option in key["options"]])
        key_html = f'<label>{key_title}<select name="{key_name}">{options}</select></label>'
    else:
        raise ValueError(f'Unknown key type "{key_type}\"')

    return f'<div class="key">{key_html}</div>'


def make_template(keys: List[dict], image_src: str, count_part: str) -> str:
    with open("index.html", encoding="utf-8") as f:
        template = f.read()

    labeled_data = get_labeled_data()
    data = labeled_data.get(image_src, {})
    title = config.get("title", "Key-value data extraction labeler")
    keys = [key_to_html(key, data) for key in keys]
    return template.format(
        title=f"{title} | {count_part}",
        image_src=image_src,
        keys="\n".join(keys)
    )


def update_labeled(image_src: str, data: dict):
    labeled_data = get_labeled_data()
    labeled_data[image_src] = data

    with open(labeled_path, "w", encoding="utf-8") as f:
        json.dump(labeled_data, f, ensure_ascii=False, indent=4)


@app.get("/")
async def index():
    images = os.listdir(images_path)

    if not images:
        return HTMLResponse("Размечать больше нечего")

    sampling = config.get("sampling", "sequential")

    if sampling == "random":
        image_src = random.choice(images)
    else:
        image_src = images[0]

    keys = config["keys"]
    count_part = f"Осталось {len(images)}"
    template = make_template(keys, image_src, count_part)

    return HTMLResponse(template)


@app.post("/save/{image_src}")
async def save(image_src: str, request: Request):
    body = await request.body()
    body = body.decode("utf-8")
    data = dict(urllib.parse.parse_qsl(body, keep_blank_values=True))

    for key in config['keys']:
        if key.get("type", "str") == "checkbox":
            data[key['name']] = key['name'] in data

    update_labeled(image_src, data)
    shutil.move(os.path.join(images_path, image_src), os.path.join(output_path, image_src))

    return RedirectResponse("/", status_code=HTTP_302_FOUND)
