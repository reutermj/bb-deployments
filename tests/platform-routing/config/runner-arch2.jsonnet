local common = import 'common.libsonnet';

{
  buildDirectoryPath: std.extVar('PWD') + '/worker-arch2/build',
  grpcServers: [{
    listenPaths: ['worker-arch2/runner'],
    authenticationPolicy: { allow: {} },
  }],
}
