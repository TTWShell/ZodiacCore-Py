import pytest

from zodiac_core.utils import strtobool


class TestStrtobool:
    @pytest.mark.parametrize("val", ["y", "yes", "t", "true", "on", "1"])
    def test_true_values(self, val):
        assert strtobool(val) is True

    @pytest.mark.parametrize("val", ["n", "no", "f", "false", "off", "0"])
    def test_false_values(self, val):
        assert strtobool(val) is False

    @pytest.mark.parametrize("val", ["", "maybe", "2", "truthy", "nope"])
    def test_invalid_raises_valueerror(self, val):
        with pytest.raises(ValueError, match="invalid truth value"):
            strtobool(val)
