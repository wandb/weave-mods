import csv
import os

import wandb
from litellm import check_valid_key


def validate_apis(wandb_api_key: str, model_a: dict[str, str], model_b: dict[str, str]):
    try:
        valid_wandb = wandb.login(key=wandb_api_key, verify=True)
        valid_model_a = check_valid_key(**model_a)
        if not valid_model_a:
            raise ValueError(f"Incorrect API Key set for Model: {model_a['model']}")
        valid_model_b = check_valid_key(**model_b)
        if not valid_model_b:
            raise ValueError(f"Incorrect API Key set for Model: {model_b['model']}")
    except ValueError as e:
        raise e
    return valid_wandb and valid_model_a and valid_model_b


async def parse_file(file_obj):
    ds_name = os.path.splitext(file_obj.filename)[0]
    file_contents = await file_obj.read()
    file_contents = file_contents.decode("utf-8").splitlines()
    reader = csv.DictReader(file_contents)
    assert (
        len(reader.fieldnames) <= 3
    ), "Only the following fields are supported: 'Prompt', 'Model A', 'Model B'"
    dataset = [line for line in reader]
    return ds_name, dataset
