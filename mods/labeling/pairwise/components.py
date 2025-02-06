from fasthtml.common import (
    Main,
    H2,
    H3,
    H4,
    Span,
    Div,
    Form,
    Label,
    Input,
    Select,
    Option,
    Script,
    Button,
    P,
    A,
    Textarea,
)

# Add this constant at the top of the file
AVAILABLE_MODELS = [
    "gpt-4o-2024-08-06",
    "chatgpt-4o-latest",
    "gpt-4o-mini-2024-07-18",
    "o1-2024-12-17",
    "o1-mini-2024-09-12",
    "o3-mini-2025-01-31",
    "o1-preview-2024-09-12",
]


def create_side_panel():
    return Form(
        Div(
            H2("Configuration", cls="text-lg font-semibold mb-2"),
            # W&B Section
            H3("Weave", cls="text-sm font-medium text-gray-700 mb-1"),
            Div(
                Label(
                    "Entity",
                    cls="block text-xs font-medium text-gray-700 mb-0.5",
                    for_="wandb_entity",
                ),
                Input(
                    type="text",
                    id="wandb_entity",
                    name="wandb_entity",
                    required=True,
                    placeholder="Enter Wandb Entity",
                    cls="w-full px-2 py-1 text-sm border border-gray-300 rounded-md mb-2",
                    oninput="validateForm()",
                ),
            ),
            Div(
                Label(
                    "Project",
                    cls="block text-xs font-medium text-gray-700 mb-0.5",
                    for_="wandb_project",
                ),
                Input(
                    type="text",
                    id="wandb_project",
                    name="wandb_project",
                    required=True,
                    placeholder="Enter Wandb Project",
                    cls="w-full px-2 py-1 text-sm border border-gray-300 rounded-md mb-2",
                    oninput="validateForm()",
                ),
            ),
            Div(
                Label(
                    "W&B API Key",
                    cls="block text-xs font-medium text-gray-700 mb-0.5",
                    for_="wandb_key",
                ),
                Input(
                    type="password",
                    id="wandb_key",
                    name="wandb_key",
                    required=True,
                    placeholder="Enter W&B API Key",
                    cls="w-full px-2 py-1 text-sm border border-gray-300 rounded-md mb-2",
                    oninput="validateForm()",
                ),
            ),
            # Model Configuration Section
            H3(
                "Model Configuration", cls="text-sm font-medium text-gray-700 mb-1 mt-3"
            ),
            Div(
                Label(
                    "Primary Model",
                    cls="block text-xs font-medium text-gray-700 mb-0.5",
                    for_="primary_model",
                ),
                Select(
                    Option("Select a model", value="", selected=True, disabled=True),
                    *[Option(model, value=model) for model in AVAILABLE_MODELS],
                    id="primary_model",
                    name="primary_model",
                    required=True,
                    cls="w-full px-2 py-1 text-sm border border-gray-300 rounded-md mb-2",
                    onchange="validateForm()",
                ),
            ),
            Div(
                Label(
                    "Primary Model API Key",
                    cls="block text-xs font-medium text-gray-700 mb-0.5",
                    for_="primary_api_key",
                ),
                Input(
                    type="password",
                    id="primary_api_key",
                    name="primary_api_key",
                    required=True,
                    placeholder="Enter API Key",
                    cls="w-full px-2 py-1 text-sm border border-gray-300 rounded-md mb-2",
                    oninput="validateForm()",
                ),
            ),
            Div(
                Label(
                    "Challenger Model",
                    cls="block text-xs font-medium text-gray-700 mb-0.5",
                    for_="challenger_model",
                ),
                Select(
                    Option("Select a model", value="", selected=True, disabled=True),
                    *[Option(model, value=model) for model in AVAILABLE_MODELS],
                    id="challenger_model",
                    name="challenger_model",
                    required=True,
                    cls="w-full px-2 py-1 text-sm border border-gray-300 rounded-md mb-2",
                    onchange="validateForm()",
                ),
            ),
            Div(
                Label(
                    "Challenger Model API Key",
                    cls="block text-xs font-medium text-gray-700 mb-0.5",
                    for_="challenger_api_key",
                ),
                Input(
                    type="password",
                    id="challenger_api_key",
                    name="challenger_api_key",
                    required=True,
                    placeholder="Enter API Key",
                    cls="w-full px-2 py-1 text-sm border border-gray-300 rounded-md mb-2",
                    oninput="validateForm()",
                ),
            ),
            # File Upload Section
            H3("Dataset", cls="text-sm font-medium text-gray-700 mb-1 mt-3"),
            Div(
                Label(
                    "Annotation File",
                    cls="block text-xs font-medium text-gray-700 mb-0.5",
                    for_="FileUpload",
                ),
                Input(
                    id="FileUpload",
                    name="FileUpload",
                    type="file",
                    required=True,
                    cls="w-full text-sm mb-2",
                    onchange="validateForm()",
                ),
            ),
            # Save Button
            Button(
                "Save Configuration",
                id="save_config",
                disabled=True,
                cls="w-full bg-gray-300 text-gray-500 font-bold py-1.5 px-4 rounded text-sm cursor-not-allowed mt-3",
                type="submit",
            ),
            # Validation Script
            Script(
                """
                function validateForm() {
                    const primary_model = document.getElementById('primary_model');
                    const challenger_model = document.getElementById('challenger_model');

                    // Update model options
                    if (primary_model.value) {
                        challenger_model.querySelectorAll('option').forEach(opt => {
                            opt.disabled = opt.value === primary_model.value || opt.value === '';
                        });
                    }
                    if (challenger_model.value) {
                        primary_model.querySelectorAll('option').forEach(opt => {
                            opt.disabled = opt.value === challenger_model.value || opt.value === '';
                        });
                    }

                    // Validate all fields
                    const fields = {
                        wandb_entity: document.getElementById('wandb_entity').value,
                        wandb_project: document.getElementById('wandb_project').value,
                        wandb_key: document.getElementById('wandb_key').value,
                        file_upload: document.getElementById('FileUpload').files.length > 0,
                        primary_model: primary_model.value && primary_model.value !== 'Select a model',
                        primary_key: document.getElementById('primary_api_key').value,
                        challenger_model: challenger_model.value && challenger_model.value !== 'Select a model',
                        challenger_key: document.getElementById('challenger_api_key').value
                    };

                    const save_button = document.getElementById('save_config');
                    const isValid = Object.values(fields).every(Boolean) &&
                                  primary_model.value !== challenger_model.value;

                    if (isValid) {
                        save_button.disabled = false;
                        save_button.classList.remove('bg-gray-300', 'text-gray-500', 'cursor-not-allowed');
                        save_button.classList.add('bg-blue-500', 'hover:bg-blue-700', 'text-white', 'cursor-pointer');
                    } else {
                        save_button.disabled = true;
                        save_button.classList.remove('bg-blue-500', 'hover:bg-blue-700', 'text-white', 'cursor-pointer');
                        save_button.classList.add('bg-gray-300', 'text-gray-500', 'cursor-not-allowed');
                    }
                }

                // Initial validation
                document.addEventListener('DOMContentLoaded', validateForm);
            """
            ),
            cls="p-4",
        ),
        method="POST",
        enctype="multipart/form-data",
        cls="h-full border-r border-gray-200 bg-gray-50",
        hx_post="/upload",
        hx_target="#main-content",
        hx_swap="innerHTML",
    )


def create_main_content():
    return Div(
        P(
            "Configure settings and upload file to begin",
            cls="text-gray-500 text-center mt-10",
        ),
        id="main-content",
        cls="flex-1 p-6",
    )


def create_layout():
    return Main(
        Div(
            # Left side panel with all configuration
            Div(create_side_panel(), cls="w-96 flex-none overflow-y-auto"),
            # Main content area
            create_main_content(),
            cls="flex h-screen",
        ),
        id="root-main",
    )


def create_annotation_page(obj_ref, idx=0):
    total_length = len(obj_ref)
    return Div(
        # Navigation Header
        Div(
            H3(
                f"Sample {idx + 1} out of {total_length}",
                cls="text-base font-semibold leading-6 text-gray-900",
            ),
            Div(
                # Previous Button
                A(
                    Span("Previous", cls="sr-only"),
                    Span("←", cls="h-5 w-5", aria_hidden="true"),
                    hx_get=f"/annotate/{idx - 1}",
                    hx_target="#main-content",
                    hx_swap="innerHTML",
                    cls="relative inline-flex items-center rounded-l-md bg-indigo-600 px-3 py-2 text-sm font-semibold text-white shadow-sm hover:bg-indigo-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-600"
                    + (" pointer-events-none opacity-50" if idx == 0 else ""),
                ),
                # Next Button
                A(
                    Span("Next", cls="sr-only"),
                    Span("→", cls="h-5 w-5", aria_hidden="true"),
                    hx_get=f"/annotate/{idx + 1}",
                    hx_target="#main-content",
                    hx_swap="innerHTML",
                    cls="relative -ml-px inline-flex items-center rounded-r-md bg-indigo-600 px-3 py-2 text-sm font-semibold text-white shadow-sm hover:bg-indigo-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-600"
                    + (
                        " pointer-events-none opacity-50"
                        if idx == total_length - 1
                        else ""
                    ),
                ),
                cls="flex-shrink-0",
            ),
            cls="flex justify-between items-center mb-4",
        ),
        # Prompt Section
        Div(
            H3("Prompt", cls="text-lg font-semibold mb-2"),
            Textarea(
                obj_ref[idx].get("prompt", ""),
                readonly=True,
                cls="w-full p-4 border border-gray-300 rounded-md mb-6 min-h-[100px] bg-gray-50",
            ),
        ),
        # Model Outputs Section
        H3("Model Outputs", cls="text-lg font-semibold mb-2"),
        Div(
            # Primary Model Output
            Div(
                H4("Primary Model", cls="text-sm font-medium text-gray-700 mb-2"),
                Textarea(
                    "Primary model output placeholder",
                    readonly=True,
                    cls="w-full p-4 border border-gray-300 rounded-md min-h-[200px] bg-gray-50",
                ),
                cls="flex-1 mr-4",
            ),
            # Challenger Model Output
            Div(
                H4("Challenger Model", cls="text-sm font-medium text-gray-700 mb-2"),
                Textarea(
                    "Challenger model output placeholder",
                    readonly=True,
                    cls="w-full p-4 border border-gray-300 rounded-md min-h-[200px] bg-gray-50",
                ),
                cls="flex-1",
            ),
            cls="flex gap-4",
        ),
        cls="p-6 max-w-6xl mx-auto",
    )
