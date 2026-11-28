# AEon: The Lantern Gate -- original RGSS3 mini-adventure.
Graphics.resize_screen(544,416)
W=544
H=416
T=32
FONT={
'A'=>[14,17,17,31,17,17,17],'B'=>[30,17,17,30,17,17,30],
'C'=>[14,17,16,16,16,17,14],'D'=>[30,17,17,17,17,17,30],
'E'=>[31,16,16,30,16,16,31],'F'=>[31,16,16,30,16,16,16],
'G'=>[14,17,16,23,17,17,15],'H'=>[17,17,17,31,17,17,17],
'I'=>[14,4,4,4,4,4,14],'J'=>[7,2,2,2,18,18,12],
'K'=>[17,18,20,24,20,18,17],'L'=>[16,16,16,16,16,16,31],
'M'=>[17,27,21,21,17,17,17],'N'=>[17,25,21,19,17,17,17],
'O'=>[14,17,17,17,17,17,14],'P'=>[30,17,17,30,16,16,16],
'Q'=>[14,17,17,17,21,18,13],'R'=>[30,17,17,30,20,18,17],
'S'=>[15,16,16,14,1,1,30],'T'=>[31,4,4,4,4,4,4],
'U'=>[17,17,17,17,17,17,14],'V'=>[17,17,17,17,17,10,4],
'W'=>[17,17,17,21,21,27,17],'X'=>[17,17,10,4,10,17,17],
'Y'=>[17,17,10,4,4,4,4],'Z'=>[31,1,2,4,8,16,31],
'0'=>[14,17,19,21,25,17,14],'1'=>[4,12,4,4,4,4,14],
'2'=>[14,17,1,2,4,8,31],'3'=>[30,1,1,14,1,1,30],
'4'=>[2,6,10,18,31,2,2],'5'=>[31,16,16,30,1,1,30],
'6'=>[14,16,16,30,17,17,14],'7'=>[31,1,2,4,8,8,8],
'8'=>[14,17,17,14,17,17,14],'9'=>[14,17,17,15,1,1,14],
':'=>[0,4,4,0,4,4,0],'-'=>[0,0,0,31,0,0,0],
'.'=>[0,0,0,0,0,12,12],'!'=>[4,4,4,4,4,0,4],
'/'=>[1,2,2,4,8,8,16],' '=>[0,0,0,0,0,0,0]}
def col(r,g,b)
  Color.new(r,g,b)
end
def rect(b,x,y,w,h,r,g,bl)
  b.fill_rect(x,y,w,h,col(r,g,bl))
end
def text(b,x,y,s,k=2,c=[232,239,218])
  s.upcase.each_char do |ch|
    (FONT[ch] || FONT[' ']).each_with_index do |row,j|
      5.times {|i| rect(b,x+i*k,y+j*k,k,k,*c) if row & (1<<(4-i)) != 0}
    end
    x+=6*k
  end
end
def panel(b,x,y,w,h)
  rect(b,x,y,w,h,12,23,38)
  rect(b,x,y,w,2,96,189,167)
  rect(b,x,y+h-2,w,2,52,96,103)
end
MAPS=[
["#################","#...............#","#.##...##.......#","#.##............#","#......##.......#","#...............#","#...##..........#","#...##..........#","#...............#","#..............>#","#################"],
["#################","#...............#","#...##....##....#","#...##....##....#","#...............#","#.....###.......#","#.....###.......#","#...............#","#...............#","#<..............#","#################"]]
def tile(x,y,room)
  return '#' if x<0 || y<0 || x>=17 || y>=11
  MAPS[room][y][x,1]
end
def person(b,x,y,kind,frame)
  px=x*T; py=y*T+64
  rect(b,px+6,py+27,20,3,20,39,42)
  coat=kind==:player ? [63,153,216] : [171,105,211]
  rect(b,px+10,py+12,12,14,*coat)
  rect(b,px+10,py+5,12,9,238,195,147)
  rect(b,px+9,py+3,14,5,52,45,66)
  rect(b,px+12,py+9,2,2,22,32,42)
  rect(b,px+18,py+9,2,2,22,32,42)
  stride=(frame/12)%2
  rect(b,px+10,py+25,5,5-stride,45,62,82)
  rect(b,px+17,py+25,5,4+stride,45,62,82)
end
def draw_world(b,room,x,y,gem,frame)
  rect(b,0,0,W,H,12,23,38)
  text(b,12,9,'AEON / THE LANTERN GATE',2,[96,224,185])
  text(b,12,34,room==0 ? '01 FOREST OUTPOST' : '02 LANTERN VAULT',2)
  11.times do |j|
    17.times do |i|
      px=i*T; py=j*T+64
      t=tile(i,j,room)
      if t=='#'
        rect(b,px,py,T,T,room==0 ? 34 : 45,room==0 ? 68 : 48,room==0 ? 60 : 81)
        rect(b,px+3,py+3,26,22,room==0 ? 52 : 65,room==0 ? 104 : 66,room==0 ? 75 : 108)
        rect(b,px+3,py+25,26,4,25,42,51)
      else
        n=(i*11+j*7)%3
        rect(b,px,py,T,T,room==0 ? 53+n*5 : 34+n*5,room==0 ? 83+n*5 : 44+n*5,room==0 ? 63+n*5 : 68+n*5)
        rect(b,px+7,py+7,2,3,86,111,91)
        if t=='>' || t=='<'
          rect(b,px+5,py+2,22,28,21,36,51)
          rect(b,px+9,py+5,14,22,89,198,175)
          rect(b,px+12,py+9,8,14,35,85,97)
        end
      end
    end
  end
  if room==0
    person(b,5,4,:npc,frame)
    text(b,5*T+10,4*T+65,'!',2,[245,205,101])
  elsif !gem
    px=12*T; py=7*T+64
    lift=(frame/15)%2*3
    rect(b,px+12,py+6-lift,8,20,242,194,91)
    rect(b,px+7,py+11-lift,18,10,242,194,91)
    rect(b,px+14,py+12-lift,4,5,255,245,181)
  end
  person(b,x,y,:player,frame)
end
screen=Sprite.new
screen.bitmap=Bitmap.new(W,H)
b=screen.bitmap
room=0; x=3; y=4; gem=false; won=false; frame=0
dialog=['FIND THE LOST LANTERN.','MOVE WITH ARROWS. A TO TALK.']
menu=false
begin
  Audio.bgm_play('Audio/BGM/Lantern',75,100)
rescue
end
loop do
  Graphics.update
  Input.update
  frame+=1
  if Input.trigger?(Input::B)
    if dialog
      dialog=nil
    else
      menu=!menu
    end
  end
  if Input.trigger?(Input::C)
    if dialog
      dialog=nil
    elsif menu
      menu=false
    elsif room==0 && (x-5).abs+(y-4).abs<=1
      if gem
        won=true
        dialog=['THE LANTERN IS HOME!','QUEST COMPLETE. THANK YOU.']
      else
        dialog=['KEEPER: FIND MY LANTERN.','THE EAST GATE LEADS TO THE VAULT.']
      end
    elsif room==1 && !gem && (x-12).abs+(y-7).abs<=1
      gem=true
      dialog=['YOU FOUND THE LANTERN!','RETURN TO THE FOREST KEEPER.']
      begin
        Audio.se_play('Audio/SE/Chime',85,100)
      rescue
      end
    else
      dialog=['EXPLORE THE PATHS.','B OPENS THE QUEST MENU.']
    end
  end
  if !dialog && !menu && frame%7==0
    dx=(Input.press?(Input::RIGHT) ? 1 : 0)-(Input.press?(Input::LEFT) ? 1 : 0)
    dy=(Input.press?(Input::DOWN) ? 1 : 0)-(Input.press?(Input::UP) ? 1 : 0)
    dy=0 if dx!=0
    nx=x+dx; ny=y+dy
    if tile(nx,ny,room)!='#' && !(room==0 && nx==5 && ny==4)
      x=nx; y=ny
    end
    if room==0 && tile(x,y,room)=='>'
      room=1; x=2; y=9
    elsif room==1 && tile(x,y,room)=='<'
      room=0; x=14; y=9
    end
  end
  if frame%3==0 || frame==1
    draw_world(b,room,x,y,gem,frame)
    if dialog
      panel(b,8,330,528,78)
      text(b,20,342,dialog[0],2)
      text(b,20,365,dialog[1],2)
      text(b,440,390,'A / B',1,[96,224,185])
    elsif menu
      panel(b,80,120,384,176)
      text(b,100,138,'QUEST LOG',3,[96,224,185])
      text(b,100,188,won ? 'COMPLETE' : 'FIND THE LANTERN',2)
      text(b,100,215,gem ? 'LANTERN: FOUND' : 'LANTERN: MISSING',2)
      text(b,100,260,'A / B TO CLOSE',2)
    end
  end
end
