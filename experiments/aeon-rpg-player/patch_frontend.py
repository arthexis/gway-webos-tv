"""Apply the AEon-only changes to the pinned RetroArch source."""
import pathlib, shutil, sys
root=pathlib.Path(sys.argv[1])
def replace(path,old,new):
    p=root/path; s=p.read_text()
    if s.count(old)!=1: raise ValueError(f'unexpected source: {path}: {old!r}')
    p.write_text(s.replace(old,new))
shutil.copyfile(pathlib.Path(__file__).with_name('select_hold.h'),root/'input/aeon_select_hold.h')
replace('runloop.c','#include "input/input_driver.h"','#include "input/input_driver.h"\n#include "input/aeon_select_hold.h"')
replace('runloop.c',"""   if (     menu_toggle_gamepad_combo != INPUT_COMBO_NONE
         && input_driver_button_combo(
               menu_toggle_gamepad_combo,
               current_time,
               &last_input))
      BIT256_SET(current_bits, RARCH_MENU_TOGGLE);""","""   if (menu_toggle_gamepad_combo == INPUT_COMBO_HOLD_SELECT)
   {
      static struct aeon_select_hold select_hold;
      if (aeon_select_update(&select_hold,
            BIT256_GET(last_input, RETRO_DEVICE_ID_JOYPAD_SELECT),
            menu_was_alive, current_time))
         BIT256_SET(current_bits, RARCH_MENU_TOGGLE);
   }
   else if (menu_toggle_gamepad_combo != INPUT_COMBO_NONE
         && input_driver_button_combo(
               menu_toggle_gamepad_combo,
               current_time,
               &last_input))
      BIT256_SET(current_bits, RARCH_MENU_TOGGLE);""")
replace('intl/msg_hash_us.h','"Hold Select (2 seconds)"','"Hold Select (3 seconds)"')
replace('intl/msg_hash_us.h','MENU_ENUM_LABEL_VALUE_CLOSE_CONTENT,\n   "Close Content"','MENU_ENUM_LABEL_VALUE_CLOSE_CONTENT,\n   "Return to Game Library"')
p=root/'menu/cbs/menu_cbs_ok.c'
s=p.read_text()
start=s.index('int action_ok_close_content(')
end=s.index('\n}',start)+2
if 'should_quit_on_close()' not in s[start:end]: raise ValueError('unexpected close action')
opening=s.index('\n{',start)+2
p.write_text(s[:opening]+ '\n   /* AEon launcher owns the library. */\n   return generic_action_ok_command(CMD_EVENT_QUIT);\n}'+s[end:])

# Keep advanced settings accessible only through an explicit submenu.
replace('menu/menu_displaylist.c',
"""static int menu_displaylist_parse_load_content_settings(
      file_list_t *list, settings_t *settings,
      bool horizontal)
{
   unsigned count         = 0;
""",
"""static int menu_displaylist_parse_load_content_settings(
      file_list_t *list, settings_t *settings,
      bool horizontal)
{
   unsigned count         = 0;

   if (!retroarch_ctl(RARCH_CTL_IS_DUMMY_CORE, NULL))
   {
      if (menu_entries_append(list,
            msg_hash_to_str(MENU_ENUM_LABEL_VALUE_RESUME_CONTENT),
            msg_hash_to_str(MENU_ENUM_LABEL_RESUME_CONTENT),
            MENU_ENUM_LABEL_RESUME_CONTENT,
            MENU_SETTING_ACTION_RUN, 0, 0, NULL))
         count++;
      if (menu_entries_append(list,
            msg_hash_to_str(MENU_ENUM_LABEL_VALUE_CLOSE_CONTENT),
            msg_hash_to_str(MENU_ENUM_LABEL_CLOSE_CONTENT),
            MENU_ENUM_LABEL_CLOSE_CONTENT,
            MENU_SETTING_ACTION_CLOSE, 0, 0, NULL))
         count++;
      if (MENU_DISPLAYLIST_PARSE_SETTINGS_ENUM(list,
            MENU_ENUM_LABEL_SETTINGS, PARSE_ACTION, false) == 0)
         count++;
      return count;
   }
""")
replace('menu/drivers/rgui.c',
"""   enum menu_action new_action = action;

   /* Scan user inputs */""",
"""   enum menu_action new_action = action;

   /* AEon: while playing, do not escape the simple pause screen. */
   if (menu_is_running_quick_menu())
   {
      switch (action)
      {
         case MENU_ACTION_CANCEL:
            return MENU_ACTION_RESUME;
         case MENU_ACTION_UP:
         case MENU_ACTION_DOWN:
         case MENU_ACTION_OK:
            return action;
         default:
            return MENU_ACTION_NOOP;
      }
   }

   /* Scan user inputs */""")

# Reuse the existing Settings action and native submenu navigation.
replace('intl/msg_hash_us.h','MENU_ENUM_LABEL_VALUE_SETTINGS,\n   "Settings"','MENU_ENUM_LABEL_VALUE_SETTINGS,\n   "Advanced Options"')

# Both controls emit a fixed, local, per-game dry-run intent.
for header in ('voice_chord.h','voice_intent.h'):
    shutil.copyfile(pathlib.Path(__file__).with_name(header),root/'input'/('aeon_'+header))
replace('runloop.c','#include "input/aeon_select_hold.h"',
    '#include "input/aeon_select_hold.h"\n#include "input/aeon_voice_chord.h"\n#include "input/aeon_voice_intent.h"')
replace('runloop.c','   last_input                       = current_bits;',
"""   last_input                       = current_bits;
   {
      static struct aeon_voice_chord chord;
      if (aeon_voice_chord_update(&chord,
            BIT256_GET(last_input, RETRO_DEVICE_ID_JOYPAD_L3),
            BIT256_GET(last_input, RETRO_DEVICE_ID_JOYPAD_R3),
            !menu_was_alive && VIDEO_HAS_FOCUS(video_st), current_time))
      {
         const char *msg = aeon_voice_send('C')
            ? "Voice Edit requested - dry run"
            : "Voice Edit unavailable for this game";
         runloop_msg_queue_push(msg, strlen(msg), 1, 180, false,
               NULL, MESSAGE_QUEUE_ICON_DEFAULT, MESSAGE_QUEUE_CATEGORY_INFO);
      }
   }""")
replace('menu/menu_displaylist.c',
"""            MENU_ENUM_LABEL_SETTINGS, PARSE_ACTION, false) == 0)
         count++;
      return count;""",
"""            MENU_ENUM_LABEL_SETTINGS, PARSE_ACTION, false) == 0)
         count++;
      if (menu_entries_append(list, "Voice Edit",
            msg_hash_to_str(MENU_ENUM_LABEL_HELP_LIST),
            MENU_ENUM_LABEL_HELP_LIST,
            MENU_SETTING_ACTION_RUN, 0, 0, NULL))
         count++;
      return count;""")
replace('menu/drivers/rgui.c','#include "../../configuration.h"',
    '#include "../../configuration.h"\n#include "../../input/aeon_voice_intent.h"')
replace('menu/drivers/rgui.c',
"""   if (menu_is_running_quick_menu())
   {
      switch (action)""",
"""   if (menu_is_running_quick_menu())
   {
      if (action == MENU_ACTION_OK && entry->enum_idx == MENU_ENUM_LABEL_HELP_LIST)
      {
         rgui_set_message(rgui, aeon_voice_send('M')
               ? "Voice Edit requested - dry run"
               : "Voice Edit unavailable for this game");
         return MENU_ACTION_NOOP;
      }
      switch (action)""")
