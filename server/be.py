import asyncio
class EchoClientProtocol:
    def __init__(self, on_con_lost):
        self.on_con_lost = on_con_lost
        self.transport = None

    def connection_made(self, transport):
        self.transport = transport
        self.transport.sendto(b'\x01' + int.to_bytes(1, 8, 'little') + bytearray.fromhex(
            '00ffff00fefefefefdfdfdfd12345678') + bytearray.fromhex('a1b6ac63b81ca9d3'))

    def datagram_received(self, data, addr):
        result = data[35:].decode()
        self.transport.close()
        self.on_con_lost.set_result(result)

    def error_received(self, exc):
        print('Error received:', exc)
        pass

    def connection_lost(self, exc):
        pass


async def main(addr,port):
    loop = asyncio.get_running_loop()

    on_con_lost = loop.create_future()

    transport, protocol = await loop.create_datagram_endpoint(
        lambda: EchoClientProtocol(on_con_lost),
        remote_addr=(addr, port))

    try:
        data = await asyncio.wait_for(on_con_lost, timeout=1)
        # https://wiki.vg/Raknet_Protocol
        # Server ID string format

        # Edition (MCPE or MCEE for Education Edition)
        edition, motd_1, protocol, version_name, player_count, max_players, unique_id, motd_2, \
        game_mode, game_mode_num, port_v4, port_v6, nothing_here = data.split(';')
        return('[BE]\n'+motd_1+' - '+motd_2 + '\n在线玩家：'+player_count+'/'+max_players+'\n游戏版本：'+edition+version_name+'\n游戏模式：'+game_mode) 
    except Exception:
        pass  
    finally:
        transport.close()