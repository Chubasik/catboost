from __future__ import print_function

import subprocess
import shutil
import os
import stat
import sys
import platform
import tempfile


sys.dont_write_bytecode = True

PL_LINUX = 'manylinux1_x86_64'
PL_MACOS = 'macosx_10_6_intel.macosx_10_9_intel.macosx_10_9_x86_64.macosx_10_10_intel.macosx_10_10_x86_64'
PL_WIN = 'win_amd64'


class PythonVersion(object):
    def __init__(self, major, minor, from_sandbox=False):
        self.major = major
        self.minor = minor
        self.from_sandbox = from_sandbox


class PythonTrait(object):
    def __init__(self, arc_root, out_root, tail_args):
        self.arc_root = arc_root
        self.out_root = out_root
        self.tail_args = tail_args
        self.python_version = mine_system_python_ver(self.tail_args)
        self.platform = mine_platform(self.tail_args)
        self.py_config, self.lang = self.get_python_info()

    def gen_cmd(self):
        cmd = [
            sys.executable, arc_root + '/ya', 'make', os.path.join(arc_root, 'catboost', 'python-package', 'catboost'),
            '--no-src-links', '-r', '--output', out_root, '-DPYTHON_CONFIG=' + self.py_config, '-DNO_DEBUGINFO', '-DOS_SDK=local',
        ]

        if not self.python_version.from_sandbox:
            cmd += ['-DUSE_ARCADIA_PYTHON=no']
            cmd += extra_opts(self._on_win())

        cmd += self.tail_args
        return cmd

    def get_python_info(self):
        if self.python_version.major == 2:
            py_config = 'python-config'
            lang = 'cp27'
        else:
            py_config = 'python3-config'
            lang = 'cp3' + str(self.python_version.minor)
        return py_config, lang

    def so_name(self):
        if self._on_win():
            return '_catboost.pyd'

        return '_catboost.so'

    def dll_ext(self):
        if self._on_win():
            return '.pyd'
        return '.so'

    def _on_win(self):
        if self.platform == PL_WIN:
            return True
        return platform.system() == 'Windows'


def mine_platform(tail_args):
    platform = find_target_platform(tail_args)
    if platform:
        return transform_platform(platform)
    return gen_platform()


def gen_platform():
    import distutils.util

    value = distutils.util.get_platform().replace("linux", "manylinux1")
    value = value.replace('-', '_').replace('.', '_')
    if 'macosx' in value:
        value = PL_MACOS
    return value


def find_target_platform(tail_args):
    try:
        target_platform_index = tail_args.index('--target-platform')
        return tail_args[target_platform_index + 1].lower()
    except ValueError:
        target_platform = [arg for arg in tail_args if '--target-platform' in arg]
        if target_platform:
            _, platform = target_platform[0].split('=')
            return platform.lower()
    return None


def transform_platform(platform):
    if 'linux' in platform:
        return PL_LINUX
    elif 'darwin' in platform:
        return PL_MACOS
    elif 'win' in platform:
        return PL_WIN
    else:
        raise Exception('Unsupported platform {}'.format(platform))


def get_version(version_py):
    exec(compile(open(version_py, "rb").read(), version_py, 'exec'))
    return locals()['VERSION']


def extra_opts(on_win=False):
    if on_win:
        py_dir = os.path.dirname(sys.executable)
        include_path = os.path.join(py_dir, 'include')
        py_libs = os.path.join(py_dir, 'libs', 'python{}{}.lib'.format(sys.version_info.major, sys.version_info.minor))
        return ['-DPYTHON_INCLUDE=/I ' + include_path, '-DPYTHON_LIBRARIES=' + py_libs]

    return []


def find_info_in_args(tail_args):
    def prepare_info(arg):
        _, version = arg.split('=')
        major, minor = version.split('.')
        py_config = 'python-config' if major == '2' else 'python3-config'
        lang = 'cp{major}{minor}'.format(major=major, minor=minor)
        return py_config, lang

    for arg in tail_args:
        if 'USE_SYSTEM_PYTHON' in arg:
            return prepare_info(arg)

    return None, None


def mine_system_python_ver(tail_args):
    for arg in tail_args:
        if 'USE_SYSTEM_PYTHON' in arg:
            _, version = arg.split('=')
            major, minor = version.split('.')
            return PythonVersion(int(major), int(minor), from_sandbox=True)
    return PythonVersion(sys.version_info.major, sys.version_info.minor)


def allow_to_write(path):
    st = os.stat(path)
    os.chmod(path, st.st_mode | stat.S_IWRITE)


def make_wheel(wheel_name, arc_root, cpu_so_path, gpu_so_path=None):
    dir_path = tempfile.mkdtemp()

    # Create py files
    python_package_dir = os.path.join(arc_root, 'catboost/python-package')
    os.makedirs(os.path.join(dir_path, 'catboost'))
    for file_name in ['__init__.py', 'version.py', 'core.py', 'datasets.py', 'utils.py', 'eval', 'widget']:
        src = os.path.join(python_package_dir, 'catboost', file_name)
        dst = os.path.join(dir_path, 'catboost', file_name)
        if os.path.isdir(src):
            shutil.copytree(src, dst)
        else:
            shutil.copy(src, dst)

    # Create so files
    so_name = PythonTrait('', '', []).so_name()
    ver = get_version(os.path.join(python_package_dir, 'catboost/version.py'))
    shutil.copy(cpu_so_path, os.path.join(dir_path, 'catboost', so_name))
    if gpu_so_path:
        gpu_dir = os.path.join(dir_path, 'catboost/gpu')
        os.makedirs(gpu_dir)
        open(os.path.join(gpu_dir, '__init__.py'), 'w').close()
        shutil.copy(gpu_so_path, os.path.join(gpu_dir, so_name))

    # Create metadata
    dist_info_dir = os.path.join(dir_path, 'catboost-{}.dist-info'.format(ver))
    shutil.copytree(os.path.join(python_package_dir, 'catboost.dist-info'), dist_info_dir)
    metadata_path = os.path.join(dist_info_dir, 'METADATA')
    allow_to_write(metadata_path)
    with open(metadata_path, 'r') as fm:
        metadata = fm.read()
    metadata = metadata.format(version=ver)
    with open(metadata_path, 'w') as fm:
        fm.write(metadata)

    # Create wheel
    shutil.make_archive(wheel_name, 'zip', dir_path)
    shutil.move(wheel_name + '.zip', wheel_name)
    shutil.rmtree(dir_path)


def build(arc_root, out_root, tail_args):
    os.chdir(os.path.join(arc_root, 'catboost', 'python-package', 'catboost'))

    py_trait = PythonTrait(arc_root, out_root, tail_args)
    ver = get_version(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'version.py'))
    so_paths = {}

    for task_type in ('GPU', 'CPU'):
        try:
            print('Trying to build {} version'.format(task_type), file=sys.stderr)
            cmd = py_trait.gen_cmd() + (['-DHAVE_CUDA=yes'] if task_type == 'GPU' else ['-DHAVE_CUDA=no'])
            print(' '.join(cmd), file=sys.stderr)
            subprocess.check_call(cmd)
            print('Build {} version: OK'.format(task_type), file=sys.stderr)
            src = os.path.join(py_trait.out_root, 'catboost', 'python-package', 'catboost', py_trait.so_name())
            dst = '.'.join([src, task_type])
            shutil.move(src, dst)
            so_paths[task_type] = dst
        except Exception:
            print('{} version build failed'.format(task_type), file=sys.stderr)

    wheel_name = os.path.join(py_trait.arc_root, 'catboost', 'python-package', 'catboost-{}-{}-none-{}.whl'.format(ver, py_trait.lang, py_trait.platform))
    make_wheel(wheel_name, arc_root, so_paths['CPU'], so_paths.get('GPU', None))

    for path in so_paths.values():
        os.remove(path)

    return wheel_name


if __name__ == '__main__':
    arc_root = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
    out_root = tempfile.mkdtemp()
    wheel_name = build(arc_root, out_root, sys.argv[1:])
    print(wheel_name)
