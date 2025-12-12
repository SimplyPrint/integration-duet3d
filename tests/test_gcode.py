from io import StringIO

from .context import GCodeCommand, GCodeBlock


def test_gcode_command_compress():
    command = GCodeCommand(code="G28", parameters=["X0", "Y0"])
    compressed = command.compress()
    assert compressed == "G28 X0 Y0"


def test_gcode_command_write_with_comments():
    command = GCodeCommand(code="G1", parameters=["X10", "Y20"])
    command.comment = ["Move to position"]
    fp = StringIO()
    command.write(fp)
    expected_output = (
        "G1 X10 Y20                                                ; Move to position\n"
    )
    assert fp.getvalue() == expected_output


def test_gcode_command_write_without_comments():
    command = GCodeCommand(code="G28", parameters=[])
    fp = StringIO()
    command.write(fp)
    expected_output = "G28\n"
    assert fp.getvalue() == expected_output


def test_gcode_block_write():
    block = GCodeBlock()
    block.comment = ["This is a block of GCode commands"]
    command1 = GCodeCommand(code="G28", parameters=[])
    command2 = GCodeCommand(code="G1", parameters=["X10", "Y20"])
    block.code = [command1, command2]
    fp = StringIO()
    block.write(fp)
    expected_output = "; This is a block of GCode commands\nG28\nG1 X10 Y20\n\n"
    assert fp.getvalue() == expected_output


def test_gcode_block_parse():
    lines = [
        "; This is a block of GCode commands",
        "G28",
        "G1 X10 Y20 ; Move to position",
        "",
    ]
    block = GCodeBlock().parse(lines)
    assert block.comment == ["This is a block of GCode commands"]
    assert len(block.code) == 2
    assert block.code[0].code == "G28"
    assert block.code[0].parameters == [""]
    assert block.code[0].comment == []
    assert block.code[1].code == "G1"
    assert block.code[1].parameters == ["X10 Y20"]
    assert block.code[1].comment == ["Move to position"]
