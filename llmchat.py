####
#### LLMCHAT.PY
#### Written by Arnaud Stevins, 12 May 2023
#### Applicable license : GNU General Public License V3


####
#### OpenAI Initialisations
####

import os
import openai
from dotenv import load_dotenv, find_dotenv

_ = load_dotenv(find_dotenv())

openai.api_key = os.getenv("OPENAI_API_KEY")

####
#### OpenAI helper functions
####


def get_completion_from_messages(messages, model="gpt-3.5-turbo", temperature=0):
    response = openai.ChatCompletion.create(
        model=model,
        messages=messages,
        temperature=temperature,  # this is the degree of randomness of the model's output
    )
    return (
        response.choices[0].message,
        response.usage.prompt_tokens,
        response.usage.completion_tokens,
    )


import tiktoken


def num_tokens_from_messages(messages, model="gpt-3.5-turbo"):
    """Returns the number of tokens used by a list of messages."""

    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        print("Warning: model not found. Using cl100k_base encoding.")
        encoding = tiktoken.get_encoding("cl100k_base")

    if model == "gpt-3.5-turbo":
        tokens_per_message = (
            4  # every message follows <|start|>{role/name}\n{content}<|end|>\n
        )
        tokens_per_name = -1  # if there's a name, the role is omitted
    elif model == "gpt-4":
        tokens_per_message = 3
        tokens_per_name = 1
    else:
        raise NotImplementedError(
            f"""num_tokens_from_messages() is not implemented for model {model}. See https://github.com/openai/openai-python/blob/main/chatml.md for information on how messages are converted to tokens."""
        )
    num_tokens = 0
    for message in messages:
        num_tokens += tokens_per_message
        for key, value in message.items():
            num_tokens += len(encoding.encode(value))
            if key == "name":
                num_tokens += tokens_per_name
    num_tokens += 3  # every reply is primed with <|start|>assistant<|message|>
    return num_tokens


####
#### Make Pretty Dialogue
####


def format_dialogue(context):
    str = ""
    for i, item in enumerate(context):
        str += f"({i}) {item['role'].upper()} : {item['content']}\n"
    return str


####
#### Main support functions
####


def reinitialize():
    global temperature, model, ptok, total_ptok
    global ctok, total_ctok, price_prompt, price_completion, context
    temperature = 0.0  # model temperature
    model = "gpt-3.5-turbo"  # model definition
    ptok = 0  # number of prompt tokens last iteration
    total_ptok = 0  # total number of prompt tokens (all iterations)
    ctok = 0  # number of completion tokens last iteration
    total_ctok = 0  # total number of completion tokens (all iterations)
    price_prompt = 0.002 / 1000.0  # in USD per prompt token
    price_completion = 0.002 / 1000.0  # in USD per completion token
    context = []  # context stores all prompts and completions
    return


reinitialize()


####
#### Main Loop for PySimpleGUI
####

import PySimpleGUI as psg
import json

psg.set_options(font=("Verdana", 12))
psg.theme("LightGreen1")

layout = [
    [psg.Text(text="Past Dialogue :")],
    [psg.Multiline(autoscroll=True, size=(100, 32), key="#Dialogue#")],
    [
        psg.Text(text="Temperature :"),
        psg.Slider(
            range=(0, 100),
            default_value=0,
            expand_x=True,
            enable_events=True,
            orientation="horizontal",
            key="-Temperature-",
        ),
    ],
    [
        psg.Text(
            text="Tokens last iteration : Prompt 0T + Completion 0T = 0T",
            key="#TokensLastIteration#",
        )
    ],
    [
        psg.Text(
            text="Total tokens used : Prompt 0T + Completion 0T =  0T",
            key="#TokensTotal#",
        )
    ],
    [psg.Text(text="Your input :")],
    [psg.Multiline(size=(100, 8), key="#Input#")],
    [
        psg.Button("Check # tokens", key="-CheckToken-"),
        psg.Text(
            text="Past dialogue : 0T + this prompt 0T = 0T",
            key="#TokensEstimate#",
        ),
    ],
    [
        psg.Button("Submit as User", key="-SubmitUser-"),
        psg.Button("Submit as System", key="-SubmitSystem-"),
    ],
    [
        psg.Button("Load chat session", key="-LoadSession-"),
        psg.Button("Save chat session", key="-SaveSession-"),
        psg.Button("Exit", key="-Exit-"),
    ],
]

window = psg.Window(
    "Welcome to the OpenAI chatbot",
    layout,
    size=(700, 900),
    resizable=True,
    finalize=True,
)

while True:
    # event handler
    event, values = window.read()
    # print(event, values)
    match event:
        case "-CheckToken-":
            msg = [{"role": "user", "content": values["#Input#"]}]
            tok = num_tokens_from_messages(msg, model=model)
            alltok = ptok + ctok
            str = f"Last dialogue : {alltok}T + estimate this prompt {tok}T => total {alltok+tok}T"
            window["#TokensEstimate#"].update(str)

        case "-SubmitUser-" | "-SubmitSystem-":
            str = "user" if (event == "-SubmitUser-") else "system"
            context.append({"role": str, "content": values["#Input#"]})
            response, ptok, ctok = get_completion_from_messages(
                context, model=model, temperature=temperature
            )
            context.append({"role": "assistant", "content": f"{response['content']}"})
            total_ptok += ptok
            total_ctok += ctok
            window["#Input#"].update("")

        case "-Temperature-":
            temperature = values["-Temperature-"] / 100.0

        case "-LoadSession-":
            loadfile = psg.popup_get_file(
                "Please select a json dialogue file",
                title="Load file Selector",
                default_path=os.getcwd(),
                default_extension="json",
                save_as=False,
            )
            if loadfile != None:
                try:
                    with open(loadfile, "r") as f:
                        reinitialize()
                        context = json.load(f)
                        f.close()
                except OSError:
                    tmp = psg.popup_error(
                        "File not found. Please check path & filename"
                    )

        case "-SaveSession-":
            savefile = psg.popup_get_file(
                "Please specify a filename (ending in .json) and location",
                title="Save file Selector",
                default_path=os.getcwd(),
                default_extension="json",
                save_as=True,
            )

            json_str = json.dumps(
                context,
                ensure_ascii=False,
                indent=4,
                sort_keys=True,
                separators=(",", ":"),
            )
            try:
                with open(savefile, "w") as f:
                    f.write(json_str)
                    f.close()
            except OSError:
                tmp = psg.popup_error("Cannot save file. Please check path & file")

        case "-Exit-" | psg.WIN_CLOSED:
            break
        case _:
            break

    # refresh all displays
    window["#Dialogue#"].update(format_dialogue(context))
    price = ptok * price_prompt + ctok * price_completion
    totalprice = total_ptok * price_prompt + total_ctok * price_completion
    window["#TokensLastIteration#"].update(
        f"Tokens last iteration : Prompt {ptok}T / Completion {ctok}T => Estimated price {price*100} cents"
    )
    window["#TokensTotal#"].update(
        f"Total tokens used : Prompt {total_ptok}T / Completion {total_ctok}T => Estimated price {totalprice*100} cents"
    )


window.close()
