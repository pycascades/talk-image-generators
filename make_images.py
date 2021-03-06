#!/usr/bin/env python3
import os
import ranges
import requests
import textwrap
from PIL import Image, ImageFont, ImageDraw, ImageOps
from datetime import datetime
from io import BytesIO

headers = {"Authorization": f"Token {os.environ.get('PRETALX_TOKEN')}"}
twitter_question_id = 1153

large_cutoff = ranges.Range(80, ranges.Inf)
med_cutoff = ranges.Range(40, 80)
small_cutoff = ranges.Range(0, 40)
cutoffs = ranges.RangeDict({
    large_cutoff: 24,
    med_cutoff: 19,
    small_cutoff: 15,
})

large_font = ranges.Range(0, 80)
med_font = ranges.Range(80, 120)
small_font = ranges.Range(120, ranges.Inf)
fonts = ranges.RangeDict({
    large_font: 60,
    med_font: 50,
    small_font: 40,
})


def get_twitter_handle(speaker):
    speaker_data = requests.get(f"https://pretalx.com/api/events/pycascades-2022/speakers/{speaker['code']}",
                                headers=headers).json()
    handle = None
    for answer in speaker_data["answers"]:
        if answer["question"]["id"] == twitter_question_id:
            handle = answer["answer"].strip("@")
            break
    return handle


def get_talks():
    # Announcements/panels
    exclude = {"MVLLML", "8YFUUC", "VVSFBR", "3C3BFP", "3HKZTJ",}
    r = requests.get("https://pretalx.com/api/events/pycascades-2022/submissions/?state=confirmed", headers=headers)
    r.raise_for_status()
    data = [talk for talk in r.json()["results"] if talk["code"] not in exclude]
    talks = []
    for blob in data:
        talktime = datetime.fromisoformat(blob["slot"]["start"]).strftime("%b %-d, %Y\n%-I:%M%p PST")
        speaker = blob["speakers"][0]
        talk = {
            "code": blob["code"],
            "title": blob["title"],
            "name": speaker["name"],
            "time": talktime,
            "pfp": speaker["avatar"],
            "twitter": get_twitter_handle(speaker),
        }
        talks.append(talk)
    return talks


def make_title(talk):
    title = talk["title"]
    cutoff = cutoffs[len(title)]
    formatted = textwrap.wrap(title, width=cutoff)
    return "\n".join(formatted)
    

def make_placard(talk):
    title = make_title(talk)
    spacing = "\n\n"
    name = talk["name"]
    print(f"Working on {name}")
    if title.startswith("Fifty shades"):
        # Special contingency for one talk that had a short title and a long speaker name
        spacing = "\n\n\n"
    text = title + spacing + talk["time"] + spacing + name
    text_font = ImageFont.truetype("fonts/Anonymous_Pro_B.ttf", size=fonts[len(text)])
    template = Image.open("talk-image-template-v2.png")
    pyc_purple_color = (98, 60, 151)
    drawing = ImageDraw.Draw(template)
    drawing.text(xy=(30, 30),
                 text=text,
                 fill=pyc_purple_color,
                 font=text_font,
                 spacing=24
                )

    # Add pfp
    size = (425, 425)
    pfp_data = BytesIO(requests.get(talk["pfp"]).content)
    pfp = Image.open(pfp_data)
    # Resize, center, and crop
    # https://gist.github.com/sigilioso/2957026#gistcomment-1409714
    pfpo = ImageOps.fit(pfp, size)
    # Crop to a circle
    # https://stackoverflow.com/a/890114/3277713
    mask = Image.new("L", size, 0)
    ellipse = ImageDraw.Draw(mask)
    ellipse.ellipse((0, 0) + size, fill=255)
    # pfpo.paste(0, mask=mask)
    pfpo.putalpha(mask)
    pfpo.convert('P', palette=Image.ADAPTIVE)


    # Determine where to paste in the new image
    y = (900 // 2) - (size[0] // 2)
    x = (1600 // 2) - (size[1] // 2)
    inner_box = (x, y)
    # Put the profile pic in the image
    template.paste(pfpo, inner_box, mask=mask)
    template.save(f"outputs/{name}.png", "PNG")


if __name__ == "__main__":
    print("Loading talks...")
    talks = get_talks()
    tweets = ""
    for talk in talks:
        tweets += "========================"
        name = talk["name"]
        twitter = talk["twitter"]
        at = f"@{twitter}" if twitter else name
        title = talk["title"]
        time = talk["time"].replace("\n", " ")
        make_placard(talk)
        tweets += f"""
TWITTER: {talk["twitter"]}
TWEET:
Looking forward to {at}'s talk, "{title}"? Sound off in the comments!
#PyCascades
https://pretalx.com/pycascades-2022/talk/{talk["code"]}/

ALT:
Talk promo picture for {name}'s talk at PyCascades 2022.
The PyCascades logo is in the top right.
The URL "2022.pycascades.com" is in the bottom right.
A picture of {name} is in the center.
The top left has the talk title: "{title}".
Below that is the talk time, {time}.
Below that is {name}'s name.

"""

    with open("outputs/tweets.txt", "w") as file:
        file.write(tweets)
    print("Done!")
