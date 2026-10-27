from cisco_show_tshoot.command_policy import validate_command


def test_interface_workflow_commands_are_allowed():
    commands = ["show ip interface brief", "show interfaces GigabitEthernet1/0/1",
                "show interfaces counters errors"]
    assert [validate_command(c) for c in commands] == commands
