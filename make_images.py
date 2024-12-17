#!/usr/bin/env python3
import os
import ranges
import requests
import textwrap
from PIL import Image, ImageFont, ImageDraw, ImageOps
from pathlib import Path
from datetime import datetime
from io import BytesIO

headers = {"Authorization": f"Token {os.environ.get('PRETALX_TOKEN')}"}
twitter_question_id = 3134
year = "2025"
event_slug = f"pycascades-{year}"
wide_image_template_path = f"templates/talk-image-template-v{year}.png"
square_image_template_path = f"templates/talk-image-template-v{year}-insta.png"


large_cutoff = ranges.Range(80, ranges.Inf)
med_cutoff = ranges.Range(40, 80)
small_cutoff = ranges.Range(0, 40)
cutoffs = ranges.RangeDict({
    large_cutoff: 24,
    med_cutoff: 18,
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
    speaker_data = requests.get(f"https://pretalx.com/api/events/{event_slug}/speakers/{speaker['code']}",
                                headers=headers).json()
    handle = None
    for answer in speaker_data["answers"]:
        if answer["question"]["id"] == twitter_question_id:
            handle = answer["answer"].strip("@")
            break
    return handle


def get_talks():
    # Announcements/panels
    exclude = {"ARGDGT"}
    r = requests.get(f"https://pretalx.com/api/events/{event_slug}/submissions/?state=confirmed", headers=headers)
    r.raise_for_status()
    data = [talk for talk in r.json()["results"] if talk["code"] not in exclude]
    talks = []
    for blob in data:
        talktime = datetime.fromisoformat(blob["slot"]["start"]).strftime("%b %-d, %Y\n%-I:%M%p PST")
        if not (speakers := blob["speakers"]):
            print(f"Talk {blob['title']} did not have a speaker!")
            continue
        for speaker in speakers:
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
    # Special contingency for talk with bad formatting
    if talk["code"] == "QRB9D7":
        cutoff = 16
    formatted = textwrap.wrap(title, width=cutoff)
    return "\n".join(formatted)
    

def make_placard(talk, template_name, suffix: str = ""):
    title = make_title(talk)
    spacing = "\n\n"
    name = talk["name"]
    original_name = name
    print(f"Working on {name}{suffix}")
    # Special contingencies for talks that have long speaker names
    #if len(name) > 20 and len(title) <= 25:
    #     spacing = "\n\n\n"
    # Special contingency for long name and short talk
    if name.startswith("Vagrant"):
        spacing = "\n\n\n"
    if len(name) > 21:
        # Get the number of spaces to skip over
        middle_space_count = (name.count(" ") // 2) + 1
        # Split by spaces up until that ammount
        split_by_space = name.split(" ", maxsplit=middle_space_count)
        # Join all of the split spaces, add a newline in between, then add the rest of the string
        name = " ".join(split_by_space[:middle_space_count]) + "\n" + split_by_space[-1]
    text = title + spacing + talk["time"] + spacing + name
    text_font = ImageFont.truetype("fonts/Anonymous_Pro_B.ttf", size=fonts[len(text)])
    template = Image.open(template_name)
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
    try:
        pfp = Image.open(pfp_data)
    except Exception as err:
        raise ValueError(f"Error with file: {talk['pfp']}") from err
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
    template.save(f"outputs/{original_name}{suffix}.png", "PNG")


if __name__ == "__main__":
    print("Loading talks...")
    (Path(__file__).parent / "outputs").mkdir(exist_ok=True)
    talks = get_talks()
    tweets = ""
    for talk in talks:
        tweets += "========================"
        name = talk["name"]
        twitter = talk["twitter"]
        at = f"@{twitter}" if twitter else name
        title = talk["title"]
        time = talk["time"].replace("\n", " ")
        if talk["pfp"] is None:
            print(f"Skipping {name} - no profile pic!")
            continue
        make_placard(talk, wide_image_template_path)
        make_placard(talk, square_image_template_path, "-insta")
        tweets += f"""
TWITTER: {talk["twitter"]}
TWEET:
Looking forward to {at}'s talk, "{title}"? Sound off in the comments!
#PyCascades
https://pretalx.com/{event_slug}/talk/{talk["code"]}/

ALT:
Talk promo picture for {name}'s talk at PyCascades {year}.
The PyCascades logo is in the top right.
The URL "{year}.pycascades.com" is in the bottom right.
A picture of {name} is in the center.
The top left has the talk title: "{title}".
Below that is the talk time, {time}.
Below that is {name}'s name.

"""

    with open("outputs/tweets.txt", "w") as file:
        file.write(tweets)
    print("Done!")
