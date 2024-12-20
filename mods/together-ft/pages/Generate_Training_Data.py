import openai
import streamlit as st
import weave
from pydantic import BaseModel
from weave import Dataset


class InputOutputPair(BaseModel):
    inp: str
    out: str


class InputOutputPairList(BaseModel):
    pairs: list[InputOutputPair]


@weave.op(name="generate_input_output_pairs")
def generate_input_output_pairs(
    task_description: str,
    num_pairs: int = 10,
    temperature: float = 1.0,
    last_pairs: list[InputOutputPair] = [],
) -> InputOutputPairList:
    """
    Generate input output pairs to train a model.

    Args:
        task_description: The description of the task to train the model on
        num_pairs: Number of input output pairs to generate (default: 3)
        temperature: The temperature value for generation (default: 1.0)
        last_pairs: A list of input output pairs that were previously generated (default: [])
    Returns:
        List of dictionaries containing input output pairs
    """

    last_pairs_str = "\n".join(
        [f"Input: {pair['input']}\nOutput: {pair['output']}" for pair in last_pairs]
    )

    prompt = f"""
    Please generate {num_pairs} input-output pairs based on the following task description.
    Try to return a diverse set of inputs and outputs that would be good for training.

    It's important to get a diverse set of inputs and outputs. Here are some examples of previous
    inputs and outputs that were used - try to avoid these and make new ones:
    {last_pairs_str}

    Make the examples completely different from the previous ones, use long strings and short strings and get creative!
    Try not to even use the same words as the previous examples.

    Return only a JSON array where each object has 'inp' and 'out' fields.

    Task Description: {task_description}
    """

    try:
        response = openai.beta.chat.completions.parse(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant that generates input-output pairs in JSON format.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=temperature,
            response_format=InputOutputPairList,
        )
        # Parse the JSON response
        input_output_pairs = response.choices[0].message.parsed
        return input_output_pairs

    except Exception as e:
        print(f"Error generating input-output pairs: {e}")
        return []


def main():
    st.title("Generate Training Data")
    task_description = st.text_input(
        "Task Description",
        value="Input is some text output is Y if it contains a joke or N if it doesn't contain a joke.",
    )
    dataset_name = st.text_input("Dataset Name", value="training_data")

    col1, col2, col3 = st.columns(3)
    with col1:
        num_examples_generated_per_call = st.number_input(
            "Number of Pairs", value=3, min_value=1, max_value=50
        )
    with col2:
        num_calls = st.number_input(
            "Number of Calls", value=1, min_value=1, max_value=10000
        )
    with col3:
        total_examples = num_examples_generated_per_call * num_calls
        st.metric(label="Total Examples", value=total_examples)

    temperature_range = st.slider(
        "Temperature Range", min_value=0.0, max_value=1.0, value=(0.0, 0.2), step=0.1
    )
    temp_min, temp_max = temperature_range

    if st.button("Generate"):
        all_input_output_pairs = []  # Store all pairs for final dataset
        for i in range(num_calls):
            # Calculate temperature for this call
            temperature = (
                temp_min + (temp_max - temp_min) * (i / (num_calls - 1))
                if num_calls > 1
                else temp_min
            )
            inp_out_pairs = generate_input_output_pairs(
                task_description,
                num_examples_generated_per_call,
                temperature=temperature,
                last_pairs=all_input_output_pairs[-10:],
            )

            # Create batch-specific list
            batch_pairs = [
                {"input": pair.inp, "output": pair.out} for pair in inp_out_pairs.pairs
            ]
            all_input_output_pairs.extend(batch_pairs)  # Add to master list

            # Show only current batch
            st.subheader(f"Batch {i+1}")
            st.dataframe(batch_pairs, use_container_width=True)

        training_data_dataset = Dataset(
            name=dataset_name,
            description=f"Dataset generated from the following task: {task_description}",
            rows=all_input_output_pairs,
        )
        published_dataset = weave.publish(training_data_dataset)

        training_data_dataset_metadata = {
            "dataset_name": dataset_name,
            "task_description": task_description,
        }
        weave.publish(training_data_dataset_metadata, name=f"{dataset_name}_metadata")
        st.write(f"Dataset published: {published_dataset.name}")


if __name__ == "__main__":
    main()
