from os.path import abspath

import ffmpy


async def camr(filename):
    ff = ffmpy.FFmpeg(
        inputs={abspath(filename): None},
        outputs={abspath(filename + '.amr'): '-ar 8000 -ab 12.2k -filter_complex channelsplit=channel_layout=mono'})
    ff.run()
    return filename + '.amr'
