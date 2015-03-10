#include "dag/dag_node.h"
#include <algorithm>
#include <glog/logging.h>

using namespace std;

namespace minerva {

DagNode::DagNode(uint64_t id) : node_id_(id) {
}

int DagNode::AddParent(DagNode* p) {
  auto pred_insert_success = p->successors_.insert(this).second;
  auto this_insert_success = predecessors_.insert(p).second;
  // Either it has already been inserted, or not
  CHECK_EQ(pred_insert_success, this_insert_success);
  return pred_insert_success;
}

}  // namespace minerva

