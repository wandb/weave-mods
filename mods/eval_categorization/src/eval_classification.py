import json
from typing import Optional

import rich
import weave
from joblib import Parallel, delayed
from rich.progress import track

from .utils import (
    serialize_input_output_objects,
    summarize_single_node,
    summarize_single_predict_and_score_call,
)


DEFAULT_STOCHASTIC_CALL_NAMES = [
    "openai.beta.chat.completions.parse",
    "openai.beta.chat.completions.create",
    "openai.chat.completions.create",
]


class EvaluationClassifier:
    def __init__(
        self,
        project: str,
        call_id: str,
        stochastic_call_names: Optional[list[str]] = [],
    ) -> None:
        self.base_call = weave.init(project).get_call(call_id=call_id)
        self.predict_and_score_calls = []
        self.predict_and_score_call_summaries = []
        self.stochastic_call_names = (
            stochastic_call_names + DEFAULT_STOCHASTIC_CALL_NAMES
        )
        self.stochastic_calls_in_predict_and_score_calls = []

    def _get_call_name_from_op_name(self, op_name: str) -> str:
        return op_name.split("/")[-1].split(":")[0]

    def register_predict_and_score_calls(
        self,
        failure_condition: str,
        max_predict_and_score_calls: Optional[int] = None,
        save_filepath: Optional[str] = None,
    ):
        count_traces_parsed = 0
        for predict_and_score_call in track(
            self.base_call.children(),
            description="Filtering predict and score calls",
            total=max_predict_and_score_calls - 1,
        ):
            if "Evaluation.summarize" in predict_and_score_call._op_name:
                break
            elif "Evaluation.predict_and_score" in predict_and_score_call._op_name:
                if eval(
                    "serialize_input_output_objects(predict_and_score_call.output)['scores']"
                    + failure_condition
                ):
                    self.predict_and_score_calls.append(predict_and_score_call)
                count_traces_parsed += 1
                if count_traces_parsed == max_predict_and_score_calls:
                    break

        rich.print(
            "INFO:\tNumber of filtered predict and score calls: ",
            len(self.predict_and_score_calls),
        )

        self.stochastic_calls_in_predict_and_score_calls = [[]] * len(
            self.predict_and_score_calls
        )
        for idx in track(
            range(len(self.predict_and_score_calls)), description="Parsing calls"
        ):
            self.predict_and_score_calls[idx] = self.parse_call(
                self.predict_and_score_calls[idx], idx
            )
        self.stochastic_calls_in_predict_and_score_calls = (
            self.stochastic_calls_in_predict_and_score_calls[0]
        )

        rich.print("INFO:\tCompleted parsing `Evaluation.predict_and_score` calls.")

        if len(self.predict_and_score_calls) > 0 and save_filepath is not None:
            self.save_calls(save_filepath)

    def parse_call(self, child_call, idx: int) -> dict:
        call_name = self._get_call_name_from_op_name(child_call._op_name)
        if call_name in self.stochastic_call_names:
            self.stochastic_calls_in_predict_and_score_calls[idx].append(
                {
                    "id": child_call.id,
                    "call_name": call_name,
                    "inputs": serialize_input_output_objects(child_call.inputs),
                    "outputs": serialize_input_output_objects(child_call.output),
                }
            )
        return {
            "id": child_call.id,
            "call_name": call_name,
            "inputs": child_call.inputs,
            "outputs": child_call.output,
            "child_calls": [
                self.parse_call(child, idx) for child in child_call.children()
            ],
        }

    def save_calls(self, filepath: str):
        with open(filepath, "w") as file:
            json.dump(self.predict_and_score_calls, file, indent=4)

    @weave.op()
    def summarize(self, node_wise: bool = False, n_jobs: int = 10) -> str:
        summarization_fn = (
            summarize_single_predict_and_score_call
            if node_wise
            else summarize_single_node
        )
        self.predict_and_score_call_summaries = Parallel(n_jobs=n_jobs)(
            delayed(summarization_fn)(call) for call in self.predict_and_score_calls
        )

        rich.print("INFO:\tCompleted summarizing `Evaluation.predict_and_score` calls.")

        return self.predict_and_score_call_summaries
