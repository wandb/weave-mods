import json
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

import rich
import weave
from joblib import Parallel, delayed
from rich.progress import track

from .utils import (
    serialize_input_output_objects,
    summarize_single_predict_and_score_call,
)


class EvaluationClassifier:
    def __init__(self, project: str, call_id: str) -> None:
        self.base_call = weave.init(project).get_call(call_id=call_id)
        self.predict_and_score_calls = []
        self.predict_and_score_call_summaries = []

    def _get_call_name_from_op_name(self, op_name: str) -> str:
        return op_name.split("/")[-1].split(":")[0]

    def register_predict_and_score_calls(
        self,
        failure_condition: str,
        max_predict_and_score_calls: Optional[int] = None,
        save_filepath: Optional[str] = None,
        max_workers: Optional[int] = None,
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

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            self.predict_and_score_calls = list(
                executor.map(self.parse_call, self.predict_and_score_calls)
            )

        rich.print("INFO:\tCompleted parsing `Evaluation.predict_and_score` calls.")

        if len(self.predict_and_score_calls) > 0 and save_filepath is not None:
            self.save_calls(save_filepath)

    def parse_call(self, child_call) -> dict:
        call_dict = {
            "id": child_call.id,
            "call_name": self._get_call_name_from_op_name(child_call._op_name),
            "inputs": serialize_input_output_objects(child_call.inputs),
            "outputs": serialize_input_output_objects(child_call.output),
            "child_calls": [self.parse_call(child) for child in child_call.children()],
        }
        return call_dict

    def save_calls(self, filepath: str):
        with open(filepath, "w") as file:
            json.dump(self.predict_and_score_calls, file, indent=4)

    @weave.op()
    def summarize(self, n_jobs: int = 10) -> str:
        def process_call(call):
            return summarize_single_predict_and_score_call(call)

        self.predict_and_score_call_summaries = Parallel(n_jobs=n_jobs)(
            delayed(process_call)(call) for call in self.predict_and_score_calls
        )

        rich.print("INFO:\tCompleted summarizing `Evaluation.predict_and_score` calls.")

        return self.predict_and_score_call_summaries
