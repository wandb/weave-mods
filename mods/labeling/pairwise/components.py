from fasthtml.common import H2, Button, Div, Form, Group, Input, Label, Main, P

"""
      <h2 class="text-base/7 font-semibold text-gray-900">Profile</h2>

<div class="flex flex-wrap -mx-3 mb-6">
    <div class="w-full md:w-1/2 px-3 mb-6 md:mb-0">
      <label class="block uppercase tracking-wide text-gray-700 text-xs font-bold mb-2" for="grid-first-name">
        First Name
      </label>
      <input class="appearance-none block w-full bg-gray-200 text-gray-700 border border-red-500 rounded py-3 px-4 mb-3 leading-tight focus:outline-none focus:bg-white" id="grid-first-name" type="text" placeholder="Jane">
      <p class="text-red-500 text-xs italic">Please fill out this field.</p>
    </div>
    <div class="w-full md:w-1/2 px-3">
      <label class="block uppercase tracking-wide text-gray-700 text-xs font-bold mb-2" for="grid-last-name">
        Last Name
      </label>
      <input class="appearance-none block w-full bg-gray-200 text-gray-700 border border-gray-200 rounded py-3 px-4 leading-tight focus:outline-none focus:bg-white focus:border-gray-500" id="grid-last-name" type="text" placeholder="Doe">
    </div>
  </div>

  <div class="flex flex-wrap -mx-3 mb-6">
    <div class="w-full px-3">
      <label class="block uppercase tracking-wide text-gray-700 text-xs font-bold mb-2" for="grid-password">
        Password
      </label>
      <input class="appearance-none block w-full bg-gray-200 text-gray-700 border border-gray-200 rounded py-3 px-4 mb-3 leading-tight focus:outline-none focus:bg-white focus:border-gray-500" id="grid-password" type="password" placeholder="******************">
      <p class="text-gray-600 text-xs italic">Make it as long and as crazy as you'd like</p>
    </div>
  </div>
"""


def create_login_page():
    form = Form(
        Div(
            H2(
                "Login",
                cls="m-10 text-base/7 font-semibold text-gray-900 justify-center",
            ),
            P(
                "Please enter the details of where you will be logging the data to.",
                cls="m-10 text-base/7 font-semibold text-gray-900 justify-center",
            ),
            Div(
                Div(
                    Label(
                        "Wandb Entity",
                        cls="block uppercase tracking-wide text-gray-700 text-xs font-bold mb-2",
                        for_="wandb_entity",
                    ),
                    Input(
                        type="text",
                        id="wandb_entity",
                        placeholder="Please enter your Wandb Entity",
                        cls="appearance-none block w-full bg-gray-200 text-gray-700 border border-red-500 rounded py-3 "
                        "px-4 mb-3 leading-tight focus:outline-none focus:bg-white",
                    ),
                    cls="w-full md:w-1/2 px-3 mb-6 md:mb-0",
                ),
                Div(
                    Label(
                        "Wandb Project",
                        cls="block uppercase tracking-wide text-gray-700 text-xs font-bold mb-2",
                        for_="wandb_project",
                    ),
                    Input(
                        type="text",
                        id="wandb_project",
                        placeholder="Please enter your Wandb Project",
                        cls="appearance-none block w-full bg-gray-200 text-gray-700 border border-red-500 rounded py-3 "
                        "px-4 mb-3 leading-tight focus:outline-none focus:bg-white",
                    ),
                    cls="w-full md:w-1/2 px-3",
                ),
                cls="flex flex-row flex-wrap m-6",
            ),
            Div(
                Div(
                    Label(
                        "W&B API Key",
                        cls="block uppercase tracking-wide text-gray-700 text-xs font-bold mb-2",
                        for_="password",
                    ),
                    Input(
                        type="password",
                        id="wandb_key",
                        placeholder="Please enter your W&B API Key",
                        cls="appearance-none block w-full bg-gray-200 text-gray-700 border border-red-500 rounded py-3 "
                        "px-4 mb-3 leading-tight focus:outline-none focus:bg-white",
                    ),
                    cls="w-full px-3",
                ),
                cls="flex flex-wrap m-6 justify-center",
            ),
            Div(
                Group(
                    Label(
                        "Annotation File",
                        for_="FileUpload",
                        cls="block uppercase tracking-wide text-gray-700 text-xs font-bold mb-2",
                    ),
                    Input(id="FileUpload", type="file"),
                    Button(
                        "Upload",
                        cls="bg-blue-500 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded",
                    ),
                ),
                cls="flex flex-wrap m-6 justify-center",
            ),
        ),
        cls="w-full h-full justify-center md:container md:mx-auto",
        hx_post="/upload",
        target_id="annotationFile",
        hx_swap="beforeend",
    )
    return form, Div(id="annotationFile")


def create_file_upload_page():
    return Main(
        H2("Upload File"),
        Form(
            Group(Input(id="annotaionFile", type="file"), Button("Upload")),
            hx_post="/upload",
            target_id="annotaionFile",
            hx_swap="beforeend",
        ),
        # Div(id="annotaionFile"),
        cls="w-full h-full justify-center md:container md:mx-auto",
    )
