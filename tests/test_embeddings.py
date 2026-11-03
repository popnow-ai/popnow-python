from popnow.types import TaskOutput

def test_vector_output_keeps_values_and_measured_usage_without_files():
    value = {"data": [{"index": 0, "embedding": [0.25, -0.5]}], "inputTokens": 7}
    output = TaskOutput.from_dict({"embeddings": value})
    assert output.embeddings == value
    assert output.raw["embeddings"] == value
    assert output.assets == []
