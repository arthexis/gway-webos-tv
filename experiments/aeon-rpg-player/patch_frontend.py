"""Apply the AEon-only changes to the pinned RetroArch source."""
import pathlib, shutil, sys
root=pathlib.Path(sys.argv[1])
def replace(path,old,new):
    p=root/path; s=p.read_text()
    if s.count(old)!=1: raise ValueError(f'unexpected source: {path}: {old!r}')
    p.write_text(s.replace(old,new))
shutil.copyfile(pathlib.Path(__file__).with_name('select_hold.h'),root/'input/aeon_select_hold.h')
replace('input/input_driver.c','#define HOLD_BTN_DELAY_SEC 2','#include "aeon_select_hold.h"\n#define HOLD_BTN_DELAY_SEC 2')
replace('input/input_driver.c',"""      case INPUT_COMBO_HOLD_SELECT:
         return input_driver_button_combo_hold(
               INPUT_COMBO_HOLD_SELECT, RETRO_DEVICE_ID_JOYPAD_SELECT, current_time, p_input);""","""      case INPUT_COMBO_HOLD_SELECT:
      {
         static struct aeon_select_hold select_hold;
         return aeon_select_update(&select_hold,
               BIT256_GET_PTR(p_input, RETRO_DEVICE_ID_JOYPAD_SELECT), current_time);
      }""")
replace('intl/msg_hash_us.h','"Hold Select (2 seconds)"','"Hold Select (3 seconds)"')
replace('intl/msg_hash_us.h','MENU_ENUM_LABEL_VALUE_CLOSE_CONTENT,\n   "Close Content"','MENU_ENUM_LABEL_VALUE_CLOSE_CONTENT,\n   "Return to Game Library"')
p=root/'menu/cbs/menu_cbs_ok.c'
s=p.read_text()
start=s.index('int action_ok_close_content(')
end=s.index('\n}',start)+2
if 'should_quit_on_close()' not in s[start:end]: raise ValueError('unexpected close action')
opening=s.index('\n{',start)+2
p.write_text(s[:opening]+ '\n   /* AEon launcher owns the library. */\n   return generic_action_ok_command(CMD_EVENT_QUIT);\n}'+s[end:])
