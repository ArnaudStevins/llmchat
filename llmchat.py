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


def get_chat_completion_from_messages(messages, model, temperature=0):
    response = openai.ChatCompletion.create(
        model=model,
        messages=messages,
        temperature=temperature,  # this is the degree of randomness of the model's output
    )
    return (
        response.choices[0].message,
        response.choices[0].finish_reason,
        response.usage.prompt_tokens,
        response.usage.completion_tokens,
    )


def get_instruct_completion_from_messages(prompt, model, temperature=0):
    response = openai.Completion.create(
        model=model, prompt=prompt, temperature=temperature, max_tokens=2048
    )
    return (
        response.choices[0].text,
        response.choices[0].finish_reason,
        response.usage.prompt_tokens,
        response.usage.completion_tokens,
    )


import tiktoken


def num_tokens_from_messages(messages, model):
    """Returns the number of tokens used by a list of messages."""

    try:
        encoding = tiktoken.encoding_for_model(model)
    except ValueError:
        print("Warning: model not found. Using cl100k_base encoding.")
        encoding = tiktoken.get_encoding("cl100k_base")

    if model[:7] == "gpt-3.5":
        tokens_per_message = (
            4  # every message follows <|start|>{role/name}\n{content}<|end|>\n
        )
        tokens_per_name = -1  # if there's a name, the role is omitted
    elif model[:5] == "gpt-4":
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
        str += f"({i}) {item['role'].upper()} : {item['content']}\n\n"
    return str


####
#### Main support functions
####


def reinitialize():
    global temperature, ptok, total_ptok, sysprompt, defaultprompt
    global ctok, total_ctok, price_prompt, price_completion, context
    temperature = 0.0  # model temperature
    ptok = 0  # number of prompt tokens last iteration
    total_ptok = 0  # total number of prompt tokens (all iterations)
    ctok = 0  # number of completion tokens last iteration
    total_ctok = 0  # total number of completion tokens (all iterations)
    context = []  # context stores all prompts and completions
    sysprompt = {}
    defaultprompt = "None"

    # load system context, if any
    try:
        with open("system.json", "r") as f:
            sysfile = json.load(f)
            f.close()

            for t in sysfile:
                name, content, default = t["name"], t["content"], t["default"]
                # print(name, "#", content, "#", default)
                sysprompt[name] = content
                if default == "True" and len(content) != 0:
                    context.append({"role": "system", "content": content})
                    defaultprompt = name

    except OSError:
        pass

    # print(list(sysprompt.keys()))
    return


####
#### Now start the code
####

import PySimpleGUI as psg
import json

reinitialize()

### List models available

listmodels = [
    ("gpt-3.5-turbo", 4097, "chat"),
    ("gpt-3.5-turbo-16k", 16385, "chat"),
    ("gpt-3.5-turbo-instruct", 4097, "instruct"),
    ("gpt-4", 8192, "chat"),
    ("gpt-4-32k", 32768, "chat"),
]
modelref = 0
(model, modelsize, modeltype) = listmodels[modelref]


####
#### Create PSG window layout
####


psg.set_options(font=("Verdana", 13))
psg.theme("LightGreen1")


layout = [
    [
        psg.Button("Change model", key="-ChangeModel-"),
        psg.Text(text=f"Model : {model}", key="#ModelName#"),
        psg.Text(text=f"Model size : {modelsize} T", key="#ModelSize#"),
        psg.Text(text=f"Model type : {modeltype}", key="#ModelType#"),
    ],
    [
        psg.Text(text="Custom instruction :"),
        psg.Combo(
            list(sysprompt.keys()),
            key="-CustomInstruction-",
            default_value=defaultprompt,
            enable_events=True,
        ),
    ],
    [psg.Text(text=f"Past dialogue :")],
    [psg.Multiline(autoscroll=True, disabled=True, size=(100, 32), key="#Dialogue#")],
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
    [psg.Button("Submit", key="-Submit-"), psg.Button("Clear", key="-Clear-")],
    [
        psg.Button("Check # tokens", key="-CheckToken-"),
        psg.Text(
            text="Past dialogue : 0T + this prompt 0T = 0T",
            key="#TokensEstimate#",
        ),
    ],
    [
        psg.Button("Load chat session", key="-LoadSession-"),
        psg.Button("Save chat session", key="-SaveSession-"),
        psg.Button("Exit", key="-Exit-"),
    ],
]

window = psg.Window(
    "LLMchat",
    layout,
    size=(700, 980),
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

        case "-Submit-":
            context.append({"role": "user", "content": values["#Input#"]})
            window["#Dialogue#"].update(format_dialogue(context))
            window.refresh()
            if modeltype == "chat":
                response, finish_reason, ptok, ctok = get_chat_completion_from_messages(
                    context, model=model, temperature=temperature
                )
                # print(finish_reason)
                if finish_reason == "stop":
                    context.append(
                        {"role": "assistant", "content": response["content"]}
                    )
                    total_ptok += ptok
                    total_ctok += ctok
                    window["#Input#"].update("")
                    window["#TokensEstimate#"].update("")
                if finish_reason == "length":
                    psg.popup(
                        "Attention - maximum number of tokens was reached, consider starting new dialogue"
                    )

            if modeltype == "instruct":
                prompt = values["#Input#"]
                (
                    response,
                    finish_reason,
                    ptok,
                    ctok,
                ) = get_instruct_completion_from_messages(
                    prompt, model=model, temperature=temperature
                )
                context.append({"role": "assistant", "content": response})
                total_ptok += ptok
                total_ctok += ctok
                window["#Input#"].update("")
                window["#TokensEstimate#"].update("")
                # and deactivate submit now
                window["-Submit-"].update(disabled=True)
                window["-Submit-"].update(button_color=("black", "red"))

        case "-Clear-":
            reinitialize()
            window["#Input#"].update("")
            window["#TokensEstimate#"].update("")
            window["-Submit-"].update(disabled=False)

        case "-Temperature-":
            temperature = values["-Temperature-"] / 100.0

        case "-ChangeModel-":
            modelref = (modelref + 1) % len(listmodels)
            (model, modelsize, modeltype) = listmodels[modelref]
            reinitialize()
            window["#Input#"].update("")
            window["#ModelName#"].update(f"Model : {model}")
            window["#ModelSize#"].update(f"Model size : {modelsize} T")
            window["#ModelType#"].update(f"Model type : {modeltype}")
            window["-Submit-"].update(disabled=False)

        case "-LoadSession-":
            loadfile = psg.popup_get_file(
                "Please select a json dialogue file",
                title="Load file Selector",
                default_path=os.getcwd() + "/chats/",
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
                "Please specify a file name (ending in .json)",
                default_path=os.getcwd() + "/chats/",
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

        case "-CustomInstruction-":
            ref = values["-CustomInstruction-"]
            content = sysprompt[ref]
            # Remove old system prompt if it exists
            if context != []:
                if context[0]["role"] == "system":
                    del context[0]
            # insert new context
            if len(content) != 0:
                context.insert(0, {"role": "system", "content": content})
            # print(content)

        case "-Exit-" | psg.WIN_CLOSED:
            break
        case _:
            break

    # refresh all displays
    window["#Dialogue#"].update(format_dialogue(context))

    window["#TokensLastIteration#"].update(
        f"Tokens last iteration : Prompt {ptok}T + Completion {ctok}T = {ptok+ctok}T / {modelsize}T (maximum)"
    )
    window["#TokensTotal#"].update(
        f"Total tokens used : Prompt {total_ptok}T + Completion {total_ctok}T"
    )


window.close()
