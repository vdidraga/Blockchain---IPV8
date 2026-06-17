from client3_miner import *

block = mine_block(
    1,
    genesis_block.prev_hash,
    [Transaction(
        bytes.fromhex("4c69624e61434c504b3ae3fc099fb56ca3b5e1de9a1c843387f2acdbb78b1bd4350ffde518068a0d246344b10d0d8c355fd0d76873e7d7f7838f3715e025af08f791324495e083331ce6"),
        bytes(0),
        1779880629,
        bytes.fromhex("1111")
    )],
    20)
print(block)