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


def test_twap_slices_update_history_without_changing_ordinary_fills():
    from pairs_desk.entry_history import merge_entry_fills
    regular=[dict(fill('A',1000,'B',100,10,0),tid=1),dict(fill('B',1001,'A',100,5,0),tid=2)]
    native=[{'coin':'A','time':2000,'side':'B','sz':'25','px':'8','tid':3},
            {'coin':'B','time':2001,'side':'A','sz':'25','px':'5','tid':4}]
    lp,sp={'szi':'125','entryPx':'9.6'},{'szi':'-125','entryPx':'5'}
    assert not entry_history('A','B',lp,sp,regular,True)['available']
    merged=merge_entry_fills(regular,native)
    history=entry_history('A','B',lp,sp,merged,True)
    assert history['available']
    assert history['initial_ratio']==2
    assert history['current_ratio']==1.92
    assert len(regular)==2
    assert len(merge_entry_fills(merged,native))==4
    assert not entry_history('A','B',lp,sp,merge_entry_fills(regular,native[:1]),True)['available']
    assert not entry_history('A','B',lp,sp,merged,False)['available']


def test_entry_history_rejects_reconstructed_average_that_disagrees_with_live_position():
    rows=[fill('A',1000,'B',10,2,0),fill('B',1001,'A',10,1,0)]
    assert not entry_history('A','B',{'szi':'10','entryPx':'3'},{'szi':'-10','entryPx':'1'},rows,True)['available']
