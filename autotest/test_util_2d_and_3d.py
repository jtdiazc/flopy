import os

import numpy as np
import pytest
from autotest.conftest import requires_pkg

from flopy.modflow import (
    Modflow,
    ModflowBas,
    ModflowDis,
    ModflowLpf,
    ModflowRiv,
    ModflowWel,
)
from flopy.utils import MfList, Transient2d, Transient3d, Util2d, Util3d


def test_transient2d():
    ml = Modflow()
    dis = ModflowDis(ml, nlay=10, nrow=10, ncol=10, nper=3)
    t2d = Transient2d(ml, (10, 10), np.float32, 10.0, "fake")
    a1 = t2d.array
    assert a1.shape == (3, 1, 10, 10), a1.shape
    t2d.cnstnt = 2.0
    assert np.array_equal(t2d.array, np.zeros((3, 1, 10, 10)) + 20.0)

    t2d[0] = 1.0
    t2d[2] = 999
    assert np.array_equal(t2d[0].array, np.ones((ml.nrow, ml.ncol)))
    assert np.array_equal(t2d[2].array, np.ones((ml.nrow, ml.ncol)) * 999)

    m4d = t2d.array
    t2d2 = Transient2d.from_4d(ml, "rch", {"rech": m4d})
    m4d2 = t2d2.array
    assert np.array_equal(m4d, m4d2)


def test_transient3d():
    nlay = 3
    nrow = 4
    ncol = 5
    nper = 5
    ml = Modflow()
    dis = ModflowDis(ml, nlay=nlay, nrow=nrow, ncol=ncol, nper=nper)

    # Make a transient 3d array of a constant value
    t3d = Transient3d(ml, (nlay, nrow, ncol), np.float32, 10.0, "fake")
    a1 = t3d.array
    assert a1.shape == (nper, nlay, nrow, ncol), a1.shape

    # Make a transient 3d array with changing entries and then verify that
    # they can be reproduced through indexing
    a = np.arange((nlay * nrow * ncol), dtype=np.float32).reshape(
        (nlay, nrow, ncol)
    )
    t3d = {0: a, 2: 1025, 3: a, 4: 1000.0}
    t3d = Transient3d(ml, (nlay, nrow, ncol), np.float32, t3d, "fake")
    assert np.array_equal(t3d[0].array, a)
    assert np.array_equal(t3d[1].array, a)
    assert np.array_equal(t3d[2].array, np.zeros((nlay, nrow, ncol)) + 1025.0)
    assert np.array_equal(t3d[3].array, a)
    assert np.array_equal(t3d[4].array, np.zeros((nlay, nrow, ncol)) + 1000.0)

    # Test changing a value
    t3d[0] = 1.0
    assert np.array_equal(t3d[0].array, np.zeros((nlay, nrow, ncol)) + 1.0)

    # Check itmp and file_entry
    itmp, file_entry_dense = t3d.get_kper_entry(0)
    assert itmp == 1
    itmp, file_entry_dense = t3d.get_kper_entry(1)
    assert itmp == -1


def test_util2d(tmpdir):
    ml = Modflow(model_ws=str(tmpdir))
    u2d = Util2d(ml, (10, 10), np.float32, 10.0, "test")
    a1 = u2d.array
    a2 = np.ones((10, 10), dtype=np.float32) * 10.0
    assert np.array_equal(a1, a2)

    # test external filenames - ascii and binary
    ascii = tmpdir / "test_a.dat"
    bin = tmpdir / "test_b.dat"
    np.savetxt(str(ascii), a1, fmt="%15.6E")
    u2d.write_bin(a1.shape, str(bin), a1, bintype="head")
    dis = ModflowDis(ml, 2, 10, 10)
    lpf = ModflowLpf(ml, hk=[str(ascii), str(bin)])
    ml.lpf.hk[1].fmtin = "(BINARY)"
    assert np.array_equal(lpf.hk[0].array, a1)
    assert np.array_equal(lpf.hk[1].array, a1)

    # test external filenames - ascii and binary with model_ws and external_path
    ml = Modflow(model_ws=str(tmpdir), external_path=str(tmpdir / "ref"))
    u2d = Util2d(ml, (10, 10), np.float32, 10.0, "test")
    ascii = tmpdir / "test_a.dat"
    bin = tmpdir / "test_b.dat"
    np.savetxt(str(ascii), a1, fmt="%15.6E")
    u2d.write_bin(a1.shape, str(bin), a1, bintype="head")
    dis = ModflowDis(ml, 2, 10, 10)
    lpf = ModflowLpf(ml, hk=[str(ascii), str(bin)])
    ml.lpf.hk[1].fmtin = "(BINARY)"
    assert np.array_equal(lpf.hk[0].array, a1)
    assert np.array_equal(lpf.hk[1].array, a1)

    # bin read write test
    bin = tmpdir / "test.bin"
    u2d.write_bin((10, 10), str(bin), u2d.array)
    a3 = u2d.load_bin((10, 10), str(bin), u2d.dtype)[1]
    assert np.array_equal(a3, a1)

    # ascii read write test
    ascii = tmpdir / "text.dat"
    u2d.write_txt((10, 10), str(ascii), u2d.array)
    a4 = u2d.load_txt((10, 10), str(ascii), u2d.dtype, "(FREE)")
    assert np.array_equal(a1, a4)

    # fixed format read/write with touching numbers - yuck!
    data = np.arange(100).reshape(10, 10)
    u2d_arange = Util2d(ml, (10, 10), np.float32, data, "test")
    u2d_arange.write_txt(
        (10, 10), bin, u2d_arange.array, python_format=[7, "{0:10.4E}"]
    )
    a4a = u2d.load_txt((10, 10), bin, np.float32, "(7E10.6)")
    assert np.array_equal(u2d_arange.array, a4a)

    # test view vs copy with .array
    a5 = u2d.array
    a5 += 1
    assert not np.array_equal(a5, u2d.array)

    # Util2d.__mul__() overload
    new_2d = u2d * 2
    assert np.array_equal(new_2d.array, u2d.array * 2)

    # test the cnstnt application
    u2d.cnstnt = 2.0
    a6 = u2d.array
    assert not np.array_equal(a1, a6)
    u2d.write_txt((10, 10), bin, u2d.array)
    a7 = u2d.load_txt((10, 10), bin, u2d.dtype, "(FREE)")
    assert np.array_equal(u2d.array, a7)


def stress_util2d(model_ws, ml, nlay, nrow, ncol):
    dis = ModflowDis(ml, nlay=nlay, nrow=nrow, ncol=ncol)
    hk = np.ones((nlay, nrow, ncol))
    vk = np.ones((nlay, nrow, ncol)) + 1.0
    # save hk up one dir from model_ws
    fnames = []
    for i, h in enumerate(hk):
        fname = os.path.join(ml._model_ws, f"test_{i}.ref")
        fnames.append(fname)
        np.savetxt(fname, h, fmt="%15.6e", delimiter="")
        vk[i] = i + 1.0

    lpf = ModflowLpf(ml, hk=fnames, vka=vk)
    # util2d binary check
    ml.lpf.vka[0].format.binary = True

    # util3d cnstnt propagation test
    ml.lpf.vka.cnstnt = 2.0
    ml.write_input()

    # check that binary is being respect - it can't get no respect!
    vka_1 = ml.lpf.vka[0]
    a = vka_1.array
    vka_1_2 = vka_1 * 2.0
    assert np.array_equal(a * 2.0, vka_1_2.array)

    if ml.external_path is not None:
        files = os.listdir(os.path.join(ml.model_ws, ml.external_path))
    else:
        files = os.listdir(ml.model_ws)

    print("\n\nexternal files: " + ",".join(files) + "\n\n")
    ml1 = Modflow.load(
        ml.namefile, model_ws=ml.model_ws, verbose=True, forgive=False
    )
    print("testing load")
    assert not ml1.load_fail
    # check that both binary and cnstnt are being respected through
    # out the write and load process.
    assert np.array_equal(ml1.lpf.vka.array, vk * 2.0)
    assert np.array_equal(ml1.lpf.vka.array, ml.lpf.vka.array)
    assert np.array_equal(ml1.lpf.hk.array, hk)
    assert np.array_equal(ml1.lpf.hk.array, ml.lpf.hk.array)

    print("change model_ws")
    ml.model_ws = os.path.join(model_ws, "new")
    ml.write_input()
    if ml.external_path is not None:
        files = os.listdir(os.path.join(ml.model_ws, ml.external_path))
    else:
        files = os.listdir(ml.model_ws)
    print("\n\nexternal files: " + ",".join(files) + "\n\n")
    ml1 = Modflow.load(
        ml.namefile, model_ws=ml.model_ws, verbose=True, forgive=False
    )
    print("testing load")
    assert not ml1.load_fail
    assert np.array_equal(ml1.lpf.vka.array, vk * 2.0)
    assert np.array_equal(ml1.lpf.hk.array, hk)

    # more binary testing
    ml.lpf.vka[0]._array[0, 0] *= 3.0
    ml.write_input()
    ml1 = Modflow.load(
        ml.namefile, model_ws=ml.model_ws, verbose=True, forgive=False
    )
    assert np.array_equal(ml.lpf.vka.array, ml1.lpf.vka.array)
    assert np.array_equal(ml.lpf.hk.array, ml1.lpf.hk.array)


def stress_util2d_for_joe_the_file_king(ml, nlay, nrow, ncol):
    dis = ModflowDis(ml, nlay=nlay, nrow=nrow, ncol=ncol)
    hk = np.ones((nlay, nrow, ncol))
    vk = np.ones((nlay, nrow, ncol)) + 1.0
    # save hk up one dir from model_ws
    fnames = []
    for i, h in enumerate(hk):
        fname = os.path.join(ml._model_ws, f"test_{i}.ref")
        fnames.append(fname)
        np.savetxt(fname, h, fmt="%15.6e", delimiter="")
        vk[i] = i + 1.0

    lpf = ModflowLpf(ml, hk=fnames, vka=vk)
    ml.lpf.vka[0].format.binary = True
    ml.lpf.vka.cnstnt = 2.0
    ml.write_input()

    assert np.array_equal(ml.lpf.hk.array, hk)
    assert np.array_equal(ml.lpf.vka.array, vk * 2.0)

    ml1 = Modflow.load(
        ml.namefile, model_ws=ml.model_ws, verbose=True, forgive=False
    )
    print("testing load")
    assert not ml1.load_fail
    assert np.array_equal(ml1.lpf.vka.array, vk * 2.0)
    assert np.array_equal(ml1.lpf.hk.array, hk)
    assert np.array_equal(ml1.lpf.vka.array, ml.lpf.vka.array)
    assert np.array_equal(ml1.lpf.hk.array, ml.lpf.hk.array)

    # more binary testing
    ml.lpf.vka[0]._array[0, 0] *= 3.0
    ml.write_input()
    ml1 = Modflow.load(
        ml.namefile, model_ws=ml.model_ws, verbose=True, forgive=False
    )
    assert np.array_equal(ml.lpf.vka.array, ml1.lpf.vka.array)
    assert np.array_equal(ml.lpf.hk.array, ml1.lpf.hk.array)


def test_util2d_external_free(tmpdir):
    ws = str(tmpdir)
    ml = Modflow(model_ws=ws)
    stress_util2d(ws, ml, 1, 1, 1)
    stress_util2d(ws, ml, 10, 1, 1)
    stress_util2d(ws, ml, 1, 10, 1)
    stress_util2d(ws, ml, 1, 1, 10)
    stress_util2d(ws, ml, 10, 10, 1)
    stress_util2d(ws, ml, 1, 10, 10)
    stress_util2d(ws, ml, 10, 1, 10)
    stress_util2d(ws, ml, 10, 10, 10)


def test_util2d_external_free_path(tmpdir):
    ws = str(tmpdir)
    ml = Modflow(model_ws=ws, external_path="ref")

    stress_util2d(ws, ml, 1, 1, 1)
    stress_util2d(ws, ml, 10, 1, 1)
    stress_util2d(ws, ml, 1, 10, 1)
    stress_util2d(ws, ml, 1, 1, 10)
    stress_util2d(ws, ml, 10, 10, 1)
    stress_util2d(ws, ml, 1, 10, 10)
    stress_util2d(ws, ml, 10, 1, 10)
    stress_util2d(ws, ml, 10, 10, 10)


def test_util2d_external_free_path_a(tmpdir):
    ml = Modflow(model_ws=str(tmpdir), external_path="ref")

    stress_util2d_for_joe_the_file_king(ml, 1, 1, 1)
    stress_util2d_for_joe_the_file_king(ml, 10, 1, 1)
    stress_util2d_for_joe_the_file_king(ml, 1, 10, 1)
    stress_util2d_for_joe_the_file_king(ml, 1, 1, 10)
    stress_util2d_for_joe_the_file_king(ml, 10, 10, 1)
    stress_util2d_for_joe_the_file_king(ml, 1, 10, 10)
    stress_util2d_for_joe_the_file_king(ml, 10, 1, 10)
    stress_util2d_for_joe_the_file_king(ml, 10, 10, 10)


def test_util2d_external_fixed(tmpdir):
    ws = str(tmpdir)
    ml = Modflow(model_ws=ws)
    ml.array_free_format = False

    stress_util2d(ws, ml, 1, 1, 1)
    stress_util2d(ws, ml, 10, 1, 1)
    stress_util2d(ws, ml, 1, 10, 1)
    stress_util2d(ws, ml, 1, 1, 10)
    stress_util2d(ws, ml, 10, 10, 1)
    stress_util2d(ws, ml, 1, 10, 10)
    stress_util2d(ws, ml, 10, 1, 10)
    stress_util2d(ws, ml, 10, 10, 10)


@pytest.mark.slow
def test_util2d_external_fixed_path(tmpdir):
    ws = str(tmpdir)
    ml = Modflow(model_ws=ws, external_path="ref")
    ml.array_free_format = False

    stress_util2d(ws, ml, 1, 1, 1)
    stress_util2d(ws, ml, 10, 1, 1)
    stress_util2d(ws, ml, 1, 10, 1)
    stress_util2d(ws, ml, 1, 1, 10)
    stress_util2d(ws, ml, 10, 10, 1)
    stress_util2d(ws, ml, 1, 10, 10)
    stress_util2d(ws, ml, 10, 1, 10)
    stress_util2d(ws, ml, 10, 10, 10)


def test_util3d(tmpdir):
    ml = Modflow(model_ws=str(tmpdir))
    u3d = Util3d(ml, (10, 10, 10), np.float32, 10.0, "test")
    a1 = u3d.array
    a2 = np.ones((10, 10, 10), dtype=np.float32) * 10.0
    assert np.array_equal(a1, a2)

    new_3d = u3d * 2.0
    assert np.array_equal(new_3d.array, u3d.array * 2)

    # test the mult list-based overload for Util3d
    mult = [2.0] * 10
    mult_array = (u3d * mult).array
    assert np.array_equal(mult_array, np.zeros((10, 10, 10)) + 20.0)
    u3d.cnstnt = 2.0
    assert not np.array_equal(a1, u3d.array)

    return


def test_arrayformat(tmpdir):
    ml = Modflow(model_ws=str(tmpdir))
    u2d = Util2d(ml, (15, 2), np.float32, np.ones((15, 2)), "test")

    fmt_fort = u2d.format.fortran
    cr = u2d.get_internal_cr()
    parsed = Util2d.parse_control_record(cr)
    print(fmt_fort, parsed["fmtin"])
    assert fmt_fort.upper() == parsed["fmtin"].upper()

    u2d.format.npl = 1
    fmt_fort = u2d.format.fortran
    cr = u2d.get_internal_cr()
    parsed = Util2d.parse_control_record(cr)
    print(fmt_fort, parsed["fmtin"])
    assert fmt_fort.upper() == parsed["fmtin"].upper()

    u2d.format.npl = 2
    u2d.format.width = 8
    fmt_fort = u2d.format.fortran
    cr = u2d.get_internal_cr()
    parsed = Util2d.parse_control_record(cr)
    print(fmt_fort, parsed["fmtin"])
    assert fmt_fort.upper() == parsed["fmtin"].upper()

    u2d.format.free = True
    u2d.format.width = 8
    fmt_fort = u2d.format.fortran
    cr = u2d.get_internal_cr()
    parsed = Util2d.parse_control_record(cr)
    print(fmt_fort, parsed["fmtin"])
    assert fmt_fort.upper() == parsed["fmtin"].upper()

    u2d.format.free = False
    fmt_fort = u2d.format.fortran
    cr = u2d.get_internal_cr()
    parsed = Util2d.parse_control_record(cr)
    print(fmt_fort, parsed["fmtin"])
    assert fmt_fort.upper() == parsed["fmtin"].upper()

    u2d.fmtin = "(10G15.6)"
    fmt_fort = u2d.format.fortran
    cr = u2d.get_internal_cr()
    parsed = Util2d.parse_control_record(cr)
    print(fmt_fort, parsed["fmtin"])
    assert fmt_fort.upper() == parsed["fmtin"].upper()

    u2d.format.binary = True
    fmt_fort = u2d.format.fortran
    cr = u2d.get_internal_cr()
    parsed = Util2d.parse_control_record(cr)
    print(fmt_fort, parsed["fmtin"])
    assert fmt_fort.upper() == parsed["fmtin"].upper()


def test_new_get_file_entry(tmpdir):
    ml = Modflow(model_ws=str(tmpdir))
    u2d = Util2d(ml, (5, 2), np.float32, np.ones((5, 2)), "test", locat=99)
    print(u2d.get_file_entry(how="internal"))
    print(u2d.get_file_entry(how="constant"))
    print(u2d.get_file_entry(how="external"))
    u2d.format.binary = True
    print(u2d.get_file_entry(how="external"))
    u2d.format.binary = False
    print(u2d.get_file_entry(how="openclose"))
    u2d.format.binary = True
    print(u2d.get_file_entry(how="openclose"))

    ml.array_free_format = False
    u2d = Util2d(ml, (5, 2), np.float32, np.ones((5, 2)), "test", locat=99)
    print(u2d.get_file_entry(how="internal"))
    print(u2d.get_file_entry(how="constant"))
    print(u2d.get_file_entry(how="external"))
    u2d.format.binary = True
    print(u2d.get_file_entry(how="external"))


def test_append_mflist(tmpdir):
    ml = Modflow(model_ws=str(tmpdir))
    dis = ModflowDis(ml, 10, 10, 10, 10)
    sp_data1 = {3: [1, 1, 1, 1.0], 5: [1, 2, 4, 4.0]}
    sp_data2 = {0: [1, 1, 3, 3.0], 8: [9, 2, 4, 4.0]}
    wel1 = ModflowWel(ml, stress_period_data=sp_data1)
    wel2 = ModflowWel(ml, stress_period_data=sp_data2)
    wel3 = ModflowWel(
        ml,
        stress_period_data=wel2.stress_period_data.append(
            wel1.stress_period_data
        ),
    )
    ml.write_input()


@requires_pkg("pandas")
def test_mflist(tmpdir, example_data_path):
    model = Modflow(model_ws=str(tmpdir))
    dis = ModflowDis(model, 10, 10, 10, 10)
    sp_data = {
        0: [[1, 1, 1, 1.0], [1, 1, 2, 2.0], [1, 1, 3, 3.0]],
        1: [1, 2, 4, 4.0],
    }
    wel = ModflowWel(model, stress_period_data=sp_data)
    spd = wel.stress_period_data

    # verify dataframe can be cast when spd.data.keys() != to ml.nper
    # verify that dataframe is cast correctly by recreating spd.data items
    df = wel.stress_period_data.get_dataframe()
    df = df.set_index(["per", "k", "i", "j"])
    for per, data in spd.data.items():
        dfdata = (
            df.xs(per, level="per")
            .dropna(
                subset=[
                    "flux",
                ],
                axis=0,
            )
            .loc[
                :,
                [
                    "flux",
                ],
            ]
            .to_records(index=True)
            .astype(data.dtype)
        )
        errmsg = f"data not equal:\n  {dfdata}\n  {data}"
        assert np.array_equal(dfdata, data), errmsg

    m4ds = model.wel.stress_period_data.masked_4D_arrays
    sp_data = MfList.masked4D_arrays_to_stress_period_data(
        ModflowWel.get_default_dtype(), m4ds
    )
    assert np.array_equal(sp_data[0], model.wel.stress_period_data[0])
    assert np.array_equal(sp_data[1], model.wel.stress_period_data[1])
    # the last entry in sp_data (kper==9) should equal the last entry
    # with actual data in the well file (kper===1)
    assert np.array_equal(sp_data[9], model.wel.stress_period_data[1])

    model = Modflow.load(
        str(example_data_path / "mf2005_test" / "swi2ex4sww.nam"),
        check=False,
        verbose=True,
    )
    m4ds = model.wel.stress_period_data.masked_4D_arrays
    sp_data = MfList.masked4D_arrays_to_stress_period_data(
        ModflowWel.get_default_dtype(), m4ds
    )

    # make a new wel file
    wel = ModflowWel(model, stress_period_data=sp_data)
    flx1 = m4ds["flux"]
    flx2 = wel.stress_period_data.masked_4D_arrays["flux"]

    flx1 = np.nan_to_num(flx1)
    flx2 = np.nan_to_num(flx2)

    assert flx1.sum() == flx2.sum()

    # test get_dataframe() on mflist obj
    sp_data3 = {
        0: [1, 1, 1, 1.0],
        1: [[1, 1, 3, 3.0], [1, 1, 2, 6.0]],
        2: [
            [1, 2, 4, 8.0],
            [1, 2, 3, 4.0],
            [1, 2, 2, 4.0],
            [1, 1, 3, 3.0],
            [1, 1, 2, 6.0],
        ],
    }
    wel4 = ModflowWel(model, stress_period_data=sp_data3)
    df = wel4.stress_period_data.get_dataframe()
    df = df.set_index(["per", "k", "i", "j"])
    assert df.loc[0, "flux"].sum() == 1.0
    assert df.loc[1, "flux"].sum() == 9.0
    assert df.loc[2, "flux"].sum() == 25.0

    sp_data4 = {
        0: [1, 1, 1, 1.0],
        1: [[1, 1, 3, 3.0], [1, 1, 3, 6.0]],
        2: [
            [1, 2, 4, 8.0],
            [1, 2, 4, 4.0],
            [1, 2, 4, 4.0],
            [1, 1, 3, 3.0],
            [1, 1, 3, 6.0],
        ],
    }
    wel5 = ModflowWel(model, stress_period_data=sp_data4)
    df = wel5.stress_period_data.get_dataframe()
    df = df.groupby(["per", "k", "i", "j"]).sum()
    assert df.loc[0, "flux"].sum() == 1.0
    assert df.loc[1, "flux"].sum() == 9.0
    assert df.loc[(2, 1, 1, 3), "flux"] == 9.0
    assert df.loc[(2, 1, 2, 4), "flux"] == 16.0

    # test squeeze option using the River package
    sp_data5 = {
        0: [
            [1, 2, 4, 1.0, 10.0, 0.5],
            [1, 2, 4, 1.5, 10.0, 0.5],
            [1, 2, 4, 1.5, 10.0, 0.5],
            [1, 1, 3, 2.0, 10.0, 0.5],
            [1, 1, 3, 4.0, 10.0, 0.5],
        ],
        1: [
            [1, 2, 4, 1.0, 10.0, 0.5],
            [1, 2, 4, 1.5, 10.0, 0.5],
            [1, 2, 4, 1.5, 10.0, 0.5],
            [1, 1, 3, 2.0, 10.0, 0.5],
            [1, 1, 3, 2.5, 10.0, 0.5],
        ],
        2: [
            [1, 2, 4, 1.0, 10.0, 0.5],
            [1, 2, 4, 1.5, 10.0, 0.5],
            [1, 2, 4, 1.5, 10.0, 0.5],
            [1, 1, 3, 2.0, 10.0, 0.5],
            [1, 1, 3, 2.5, 10.0, 0.5],
        ],
        3: [
            [1, 2, 4, 1.0, 20.0, 0.5],
            [1, 2, 4, 1.5, 20.0, 0.5],
            [1, 2, 4, 1.5, 20.0, 0.5],
            [1, 1, 3, 2.0, 20.0, 0.5],
            [1, 1, 3, 2.5, 20.0, 0.5],
        ],
        4: [
            [1, 2, 4, 1.0, 20.0, 0.5],
            [3, 3, 3, 1.0, 20.0, 0.5],
        ],
    }
    riv = ModflowRiv(model, stress_period_data=sp_data5)
    df = riv.stress_period_data.get_dataframe(squeeze=True)
    assert len(df.groupby("per").sum()) == 4
    assert df.groupby("per")["cond"].sum().loc[3] == 100.0
    assert df.groupby("per")["stage"].mean().loc[0] == 2.0
    assert df.groupby(["k", "i", "j"])["rbot"].count()[(1, 2, 4)] == 10


def test_how(tmpdir):
    ml = Modflow(model_ws=str(tmpdir))
    ml.array_free_format = False
    dis = ModflowDis(ml, nlay=2, nrow=10, ncol=10)

    arr = np.ones((ml.nrow, ml.ncol))
    u2d = Util2d(ml, arr.shape, np.float32, arr, "test", locat=1)
    print(u2d.get_file_entry())
    u2d.how = "constant"
    print(u2d.get_file_entry())
    u2d.fmtin = "(binary)"
    print(u2d.get_file_entry())


def test_util3d_reset():
    ml = Modflow()
    ml.array_free_format = False
    dis = ModflowDis(ml, nlay=2, nrow=10, ncol=10)
    bas = ModflowBas(ml, strt=999)
    arr = np.ones((ml.nlay, ml.nrow, ml.ncol))
    ml.bas6.strt = arr


@requires_pkg("pandas")
def test_mflist_fromfile(tmpdir):
    """test that when a file is passed to stress period data,
    the .array attribute will load the file
    """
    import pandas as pd

    wel_data = pd.DataFrame(
        [(0, 1, 2, -50.0), (0, 5, 5, -50.0)], columns=["k", "i", "j", "flux"]
    )
    wpth = os.path.join(tmpdir, "wel_000.dat")
    wel_data.to_csv(
        wpth,
        index=False,
        sep=" ",
        header=False,
    )

    nwt_model = Modflow(
        "nwt_testmodel",
        verbose=True,
        model_ws=str(tmpdir),
    )
    dis = ModflowDis(
        nwt_model,
        nlay=1,
        nrow=10,
        ncol=10,
        delr=500.0,
        delc=500.0,
        top=100.0,
        botm=50.0,
    )
    wel = ModflowWel(nwt_model, stress_period_data={0: wpth})
    flx_array = wel.stress_period_data.array["flux"][0]
    for k, i, j, flx in zip(wel_data.k, wel_data.i, wel_data.j, wel_data.flux):
        assert flx_array[k, i, j] == flx
