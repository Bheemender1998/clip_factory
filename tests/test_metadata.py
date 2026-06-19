from types import SimpleNamespace

from clipper import metadata


def test_write_metadata_returns_parsed(monkeypatch):
    result = metadata.ClipMeta(title="T", caption="C", hashtags=["#a", "#b"])

    class FakeClient:
        class messages:
            @staticmethod
            def parse(**kwargs):
                assert kwargs["output_format"] is metadata.ClipMeta
                return SimpleNamespace(
                    parsed_output=result,
                    usage=SimpleNamespace(input_tokens=5, output_tokens=3),
                )

    got = metadata.write_metadata("a clip about cats", "Cats Win", client=FakeClient())
    assert got.title == "T"
    assert got.hashtags == ["#a", "#b"]
