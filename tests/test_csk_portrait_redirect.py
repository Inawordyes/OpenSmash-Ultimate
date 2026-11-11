"""The portrait a redirected costume asks for (runtime/hle_skyline.c redirect_for_path, used by
ui_path): the game asks by the fighter's own ui_chara and the match's costume (Mario, c26); the
answer is the character whose costumes hold it. With two characters on one fighter's costumes, their
64-costume windows overlap: the one whose costumes start nearest below the costume asked is meant,
whichever was added first. No game files needed: the function is compiled from the runtime's source."""
from pathlib import Path
import os
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

MARIO = 0xDBA1F2B6B            # made-up 40-bit values: only equality matters here
NESS = 0xD4F1E9A22
EARLY = 0x1111111111           # a character on Mario's c08..
POPPLE = 0xFA91015E3           # hash40("ui_chara_popple"): a .prcxml echo on Mario's c24..
NINTEN = 0xFEE536919           # hash40("ui_chara_ninten"): a CSK character on Ness's c120..


def function_source(name):
    source = (ROOT / "runtime/hle_skyline.c").read_text(encoding="utf-8")
    begin = source.index(f"static Redirect *{name}(")
    end = source.index("\n}\n", begin) + 3
    return source[begin:end]


HARNESS = r'''
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
typedef uint64_t u64; typedef uint32_t u32;
typedef struct { u64 ui_chara, base; int start; } Redirect;
static Redirect redirects[64];
static u32 redirect_n;
%(function)s
/* argv: the hash asked, the costume asked, then the table in its order: "ui_chara base start" each */
int main(int argc, char **argv) {
    for (int i = 3; i + 2 < argc; i += 3)
        redirects[redirect_n++] = (Redirect){strtoull(argv[i], 0, 16), strtoull(argv[i + 1], 0, 16), atoi(argv[i + 2])};
    Redirect *r = redirect_for_path(strtoull(argv[1], 0, 16), atoi(argv[2]));
    if (r) printf("%%llx %%d\n", (unsigned long long)r->ui_chara, atoi(argv[2]) - r->start);
    else printf("none\n");
    return 0;
}
'''

ON_MARIO_C08 = (EARLY, MARIO, 8)
ON_MARIO_C24 = (POPPLE, MARIO, 24)
ON_NESS_C120 = (NINTEN, NESS, 120)


class PortraitRedirectTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        compiler = shutil.which("clang") or shutil.which("cc")
        if not compiler:
            raise unittest.SkipTest("C compiler not installed")
        cls.tmp = tempfile.TemporaryDirectory(prefix="csk portrait test ")
        src = Path(cls.tmp.name) / "portrait.c"
        src.write_text(HARNESS % {"function": function_source("redirect_for_path")}, encoding="utf-8")
        cls.exe = Path(cls.tmp.name) / ("portrait.exe" if os.name == "nt" else "portrait")
        subprocess.run([compiler, "-std=c11", "-Wall", "-Werror", "-o", str(cls.exe), str(src)], check=True)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def asked(self, h, costume, *table):
        args = [str(self.exe), f"{h:x}", str(costume)] + [f"{v:x}" if i < 2 else str(v) for row in table for i, v in enumerate(row)]
        return subprocess.run(args, check=True, capture_output=True, text=True).stdout.split()

    def test_the_fighters_costume_gives_the_character_and_its_own_color(self):
        self.assertEqual(self.asked(NESS, 121, ON_NESS_C120), [f"{NINTEN:x}", "1"])

    def test_the_characters_own_hash_gives_its_own_color(self):
        self.assertEqual(self.asked(POPPLE, 26, ON_MARIO_C08, ON_MARIO_C24), [f"{POPPLE:x}", "2"])

    def test_of_two_characters_on_one_fighter_the_nearest_start_below_wins(self):
        # Mario c26 is Popple's c02 (c24..), also inside the 64-costume window of the character on c08..
        self.assertEqual(self.asked(MARIO, 26, ON_MARIO_C08, ON_MARIO_C24), [f"{POPPLE:x}", "2"])

    def test_the_order_the_characters_were_added_in_does_not_matter(self):
        self.assertEqual(self.asked(MARIO, 26, ON_MARIO_C24, ON_MARIO_C08), [f"{POPPLE:x}", "2"])
        self.assertEqual(self.asked(MARIO, 10, ON_MARIO_C24, ON_MARIO_C08), [f"{EARLY:x}", "2"])
        self.assertEqual(self.asked(MARIO, 10, ON_MARIO_C08, ON_MARIO_C24), [f"{EARLY:x}", "2"])

    def test_a_costume_outside_every_window_is_left_alone(self):
        self.assertEqual(self.asked(MARIO, 7, ON_MARIO_C08, ON_MARIO_C24), ["none"])    # the fighter's own
        self.assertEqual(self.asked(MARIO, 87, ON_MARIO_C24), [f"{POPPLE:x}", "63"])    # the window's last
        self.assertEqual(self.asked(MARIO, 88, ON_MARIO_C24), ["none"])                 # one past it

    def test_another_fighters_costume_is_left_alone(self):
        self.assertEqual(self.asked(NESS, 26, ON_MARIO_C08, ON_MARIO_C24), ["none"])


if __name__ == "__main__":
    unittest.main()
