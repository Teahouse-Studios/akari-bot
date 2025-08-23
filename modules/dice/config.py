from . import dice


@dice.config()
class DiceConfig:
    dice_limit: int = 100
    dice_roll_limit: int = 10
    dice_count_limit: int = 10
    dice_output_count: int = 50
    dice_output_len: int = 200
    dice_output_digit: int = 9
    dice_detail_count: int = 5
