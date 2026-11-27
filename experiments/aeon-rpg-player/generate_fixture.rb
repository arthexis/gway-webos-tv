require 'fileutils'
require 'zlib'
abort 'usage: ruby generate_fixture.rb NEW_DIRECTORY' unless ARGV.size == 1
root = ARGV.first
Dir.mkdir(root)
Dir.mkdir(File.join(root, 'Data'))
script = <<~'RGSS'
  Graphics.resize_screen(544, 416)
  sprite = Sprite.new
  sprite.bitmap = Bitmap.new(24, 24)
  sprite.bitmap.fill_rect(0, 0, 24, 24, Color.new(70, 200, 120))
  sprite.x = 260
  sprite.y = 196
  active = false
  loop do
    Graphics.update
    Input.update
    sprite.x = [[sprite.x + (Input.press?(Input::RIGHT) ? 2 : 0) - (Input.press?(Input::LEFT) ? 2 : 0), 0].max, 520].min
    sprite.y = [[sprite.y + (Input.press?(Input::DOWN) ? 2 : 0) - (Input.press?(Input::UP) ? 2 : 0), 0].max, 392].min
    if Input.trigger?(Input::C)
      active = !active
      sprite.bitmap.fill_rect(0, 0, 24, 24, active ? Color.new(230, 150, 50) : Color.new(70, 200, 120))
    end
    break if Input.trigger?(Input::B)
  end
  sprite.bitmap.dispose
  sprite.dispose
RGSS
File.binwrite(File.join(root, 'Data', 'Scripts.rvdata2'), Marshal.dump([[1, 'AEon smoke', Zlib::Deflate.deflate(script)]]))
File.write(File.join(root, 'Game.ini'), "[Game]\nLibrary=System\\RGSS301.dll\nScripts=Data\\Scripts.rvdata2\nTitle=AEon VX Ace smoke fixture\nRTP=\n")
