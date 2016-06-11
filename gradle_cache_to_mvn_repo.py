import sys
import os
import subprocess
import glob
import shutil
import argparse

class ArtifactEntry:
    def __init__(self, file_name, location):
        self.file_name = file_name
        self.location = location

    def get_full_path(self):
        return self.location + '/' + self.file_name

    def __hash__(self):
        return hash((self.file_name, self.location))

    def __eq__(self, other):
        return (self.file_name, self.location) == (other.file_name, other.location)

    def __ne__(self, other):
        return not(self == other)


class Artifact:
    def __init__(self, id):
        self.id = id
        self.versioned_entries = {}

    def append_entry(self, version, entry):
        if version not in self.versioned_entries:
            self.versioned_entries[version] = [entry]
        self.versioned_entries[version].append(entry)

    def get_versions(self):
        return self.versioned_entries.keys()

    def get_entries(self, version):
        return self.versioned_entries[version]


class Group:
    def __init__(self, id, path):
        self.id = id
        self.path = path
        self.artifacts = []

    def merge(self, other_group):
        if self.id.equals(other_group.id):
            for artifact in other_group.artifacts:
                self.add_artifact(artifact)

    def add_artifact(self, artifact):
        if artifact not in self.artifacts:
            self.artifacts.append(artifact)

    def get_as_path(self):
        return self.id.replace('.', '/')


class ArtifactRepo:
    def __init__(self):
        self.groups = {}

    def __create_group_path(self, group_path):
        if not os.path.exists(group_path):
            os.makedirs(group_path)

    def add_group(self, group):
        if group.id in self.groups:
            self.groups[group.id].merge(group)
        else:
            self.groups[group.id] = group


class GradleCache:
    def __init__(self, cache_dir=None):
        self.path = None
        self.module_paths = None
        self.repo = ArtifactRepo()
        if cache_dir is not None:
            self.load(cache_dir)

    def load(self, cache_dir):
        self.path = cache_dir
        self.module_paths = os.path.join(self.path, "caches/modules-*/files-*")
        self.__load_repo()

    def __load_repo(self):
        self.__generate_groups()
        self.__generate_artifacts()

    def __generate_groups(self):
        for module_path in glob.glob(self.module_paths):
            for group_id in os.listdir(module_path):
                self.repo.add_group(Group(group_id, os.path.join(module_path, group_id)))

    def __load_artifact_entries_by_version(self, artifact, artifact_path, version):
        artifact_version_path = os.path.join(artifact_path, version)
        for gradle_hash in os.listdir(artifact_version_path):
            gradle_hash_path = os.path.join(artifact_version_path, gradle_hash)
            for file in os.listdir(gradle_hash_path):
                artifact.append_entry(version=version, entry=ArtifactEntry(file, gradle_hash_path))

    def __load_artifact(self, artifact_path, artifact_id):
        artifact = Artifact(artifact_id)
        for artifact_version in os.listdir(artifact_path):
            self.__load_artifact_entries_by_version(artifact, artifact_path, artifact_version)
        return artifact

    def __generate_artifacts(self):
        for group_id in self.repo.groups:
            group_path = self.repo.groups[group_id].path
            for artifact_id in os.listdir(group_path):
                artifact_path = os.path.join(group_path, artifact_id)
                artifact = self.__load_artifact(artifact_path, artifact_id)
                self.repo.groups[group_id].add_artifact(artifact)


class ArtifactRepoWriter:
    def write(self, repo, target_dir):
        pass


class MavenRepoWriter(ArtifactRepoWriter):
    def write(self, repo, target_dir):
        if not os.path.exists(target_dir):
            os.makedirs(target_dir)
        for group_id in repo.groups:
            group = repo.groups[group_id]
            group_path = os.path.join(target_dir, group.get_as_path())
            for artifact in group.artifacts:
                artifact_path = os.path.join(group_path, artifact.id)
                for version in artifact.versioned_entries:
                    version_path = os.path.join(artifact_path, version)
                    for entry in artifact.versioned_entries[version]:
                        if not os.path.exists(version_path):
                            os.makedirs(version_path)
                        entry_path = os.path.join(version_path, entry.file_name)
                        shutil.copyfile(entry.get_full_path(), entry_path)


def cleanup_mvn_dir(mvn_dir):
    shutil.rmtree(mvn_dir)

def main():
    parser = argparse.ArgumentParser(description='Generate local maven repository from a gradle cache.')
    parser.add_argument('--gradle_cache_dir', metavar='cache dir', help='Path to Gradle cache directory', required=True)
    parser.add_argument('--target_mvn_dir', metavar='maven repository dir', help='Path to the local maven repository', required=True)
    parser.add_argument('--pre_clean_mvn_dir', help='Remove target_mvn_dir before generating the maven repository.', action='store_true')
    args = parser.parse_args()

    gradle_cache = GradleCache()
    gradle_cache.load(args.gradle_cache_dir)

    if args.pre_clean_mvn_dir:
        cleanup_mvn_dir(args.target_mvn_dir)

    mvn_writer = MavenRepoWriter()
    mvn_writer.write(target_dir=args.target_mvn_dir, repo=gradle_cache.repo)

if __name__ == "__main__":
    main()
