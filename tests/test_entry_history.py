from pairs_desk.entry_history import entry_history


def fill(coin, time, side, sz, px, start):
    return {'coin':coin,'time':time,'side':side,'sz':str(sz),'px':str(px),'startPosition':str(start)}


def test_step_average_and_reduction():
    rows=[fill('A',1000,'B',10,2,0),fill('B',1001,'A',10,1,0),
          fill('A',2000,'B',10,1,10),fill('B',2001,'A',10,1,-10),
          fill('A',3000,'A',5,1.1,20),fill('B',3001,'B',5,1,-20)]
    result=entry_history('A','B',{'szi':'15'},{'szi':'-15'},rows,True)
    assert result['available']
    assert result['initial_ratio']==2
    assert result['current_ratio']==1.5
    assert result['steps'][-1]['ratio']==1.5


def test_incomplete_does_not_fabricate_steps():
    assert not entry_history('A','B',{'szi':'1'},{'szi':'-1'},[],False)['available']
