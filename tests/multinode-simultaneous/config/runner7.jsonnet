local common = import 'common.libsonnet';

{
  buildDirectoryPath: std.extVar('PWD') + '/worker7/build',
  grpcServers: [{
    listenPaths: ['worker7/runner'],
    authenticationPolicy: { allow: {} },
  }],
}
